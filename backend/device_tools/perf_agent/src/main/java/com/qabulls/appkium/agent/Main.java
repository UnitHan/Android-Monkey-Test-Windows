package com.qabulls.appkium.agent;

import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.PrintStream;
import java.io.UnsupportedEncodingException;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * Appkium Perf 의 Android 수집기. APK 설치 없이 shell 권한으로 기기에서 실행한다.
 *
 *     adb push appkium-android.jar /data/local/tmp/
 *     adb shell CLASSPATH=/data/local/tmp/appkium-android.jar app_process / com.qabulls.appkium.agent.Main monitor --package <패키지>
 *
 * 표준 출력에 JSON 한 줄씩 쓴다.
 *  - {"type":"hello","version":…,"protocol":1,"sdk":…}  시작할 때 한 번
 *  - {"type":"sample",…}                                 [interval] 마다
 *  - {"type":"error","code":…,"message":…}               끝나기 직전
 *
 * PC 가 연결을 끊으면 스스로 끝난다 — 기기에 프로세스가 남지 않게 하기 위해서다. adb(특히 무선 adb)는 PC 쪽 adb 가
 * 죽어도 기기 프로세스를 끝내 주지 않아서 세 가지를 함께 본다: 표준 입력 EOF, 표준 출력 쓰기 실패, PC 의 생존 신호.
 * PC 는 1초마다 표준 입력에 한 바이트를 보낸다. 한 번이라도 받은 뒤 [HEARTBEAT_TIMEOUT_MS] 동안 끊기면 끝낸다
 * (표준 입력을 넘겨주지 않는 환경에서 곧바로 죽지 않도록, 처음 받기 전에는 시간을 재지 않는다).
 */
public final class Main {
    static final String VERSION = "0.2.0";
    static final int PROTOCOL = 1;

    static final long HEARTBEAT_TIMEOUT_MS = 5_000L;

    private static PrintStream out;
    private static volatile long lastHeartbeatMs;

    private Main() {}

    public static void main(String[] args) {
        try {
            out = new PrintStream(new FileOutputStream(FileDescriptor.out), false, "UTF-8");
        } catch (UnsupportedEncodingException e) {
            out = System.out;
        }
        String cmd = args.length > 0 ? args[0] : "";
        try {
            if (cmd.equals("version")) {
                emit(hello());
            } else if (cmd.equals("monitor")) {
                monitor(args);
            } else if (cmd.equals("icons")) {
                icons(args);
            } else {
                emit(Json.type("error").put("code", "usage").put("message", "usage: version | monitor --package <name> [--interval ms] | icons [--size px] <package>…"));
                System.exit(2);
            }
        } catch (Throwable t) {
            emit(Json.type("error").put("code", "crash").put("message", String.valueOf(t)));
            System.exit(1);
        }
    }

    private static Json hello() {
        return Json.type("hello")
            .put("version", VERSION)
            .put("protocol", PROTOCOL)
            .put("pid", selfPid())
            .put("sdk", Parse.toInt(Sys.INSTANCE.exec(3_000, "getprop", "ro.build.version.sdk")));
    }

    private static void monitor(String[] args) throws InterruptedException {
        String pkg = arg(args, "--package");
        if (pkg == null || pkg.isEmpty()) {
            emit(Json.type("error").put("code", "usage").put("message", "--package is required"));
            System.exit(2);
        }
        long interval = parseLong(arg(args, "--interval"), 1_000L);
        long slowInterval = parseLong(arg(args, "--slow-interval"), 5_000L);

        final Sampler sampler = new Sampler(Sys.INSTANCE, pkg);
        emit(hello().put("package", pkg).put("interval", interval));

        watchStdin();

        ScheduledExecutorService slow = Executors.newSingleThreadScheduledExecutor();
        slow.scheduleWithFixedDelay(new Runnable() {
            @Override public void run() {
                try { sampler.refreshSlow(); } catch (Throwable ignored) { }
            }
        }, 0, slowInterval, TimeUnit.MILLISECONDS);

        ScheduledExecutorService fast = Executors.newSingleThreadScheduledExecutor();
        fast.scheduleAtFixedRate(new Runnable() {
            @Override public void run() {
                try {
                    emit(sampler.tick(System.nanoTime() / 1_000_000L));
                } catch (Throwable t) {
                    // 예약 작업은 예외 한 번에 영구히 멈춘다. 다음 표본은 계속 돌아야 하므로 알리고 넘어간다.
                    emit(Json.type("warn").put("code", "sample").put("message", String.valueOf(t)));
                }
            }
        }, 0, interval, TimeUnit.MILLISECONDS);

        fast.awaitTermination(Long.MAX_VALUE, TimeUnit.DAYS);
    }

    /** 앱 아이콘 · 이름. Android API 가 필요한 코드라 Android SDK 로 빌드한 수집기에만 있다. */
    private static void icons(String[] args) throws Exception {
        Class<?> type;
        try {
            type = Class.forName("com.qabulls.appkium.agent.AppIcons");
        } catch (ClassNotFoundException e) {
            emit(Json.type("error").put("code", "unsupported").put("message", "this collector was built without app icons"));
            System.exit(2);
            return;
        }
        try {
            type.getMethod("main", String[].class).invoke(null, (Object) args);
        } catch (java.lang.reflect.InvocationTargetException e) {
            throw e.getCause() instanceof Exception ? (Exception) e.getCause() : e;
        }
        System.exit(0);
    }

    /** 표준 입력이 닫히거나 PC 의 생존 신호가 끊기면 끝낸다. */
    private static void watchStdin() {
        Thread reader = new Thread(new Runnable() {
            @Override public void run() {
                try {
                    while (System.in.read() >= 0) lastHeartbeatMs = System.nanoTime() / 1_000_000L;
                } catch (Throwable ignored) { }
                System.exit(0);
            }
        }, "stdin-watch");
        reader.setDaemon(true);
        reader.start();

        Thread watchdog = new Thread(new Runnable() {
            @Override public void run() {
                while (true) {
                    try { Thread.sleep(1_000L); } catch (InterruptedException e) { return; }
                    long last = lastHeartbeatMs;
                    if (last != 0L && System.nanoTime() / 1_000_000L - last > HEARTBEAT_TIMEOUT_MS) {
                        emit(Json.type("error").put("code", "heartbeat").put("message", "PC heartbeat lost"));
                        System.exit(0);
                    }
                }
            }
        }, "heartbeat-watch");
        watchdog.setDaemon(true);
        watchdog.start();
    }

    /** 이 수집기의 pid. PC 가 측정을 멈출 때 이 프로세스만 끝내는 데 쓴다. */
    private static Integer selfPid() {
        String stat = Sys.INSTANCE.read("/proc/self/stat");
        if (stat == null) return null;
        int sp = stat.indexOf(' ');
        return Parse.toInt(sp < 0 ? stat : stat.substring(0, sp));
    }

    static synchronized void emit(Json line) {
        out.println(line.toString());
        out.flush();
        // PC 가 읽기를 멈췄으면(파이프 끊김) 더 돌 이유가 없다.
        if (out.checkError()) System.exit(0);
    }

    private static String arg(String[] args, String name) {
        for (int i = 0; i < args.length - 1; i++) if (args[i].equals(name)) return args[i + 1];
        return null;
    }

    private static long parseLong(String s, long fallback) {
        Long v = Parse.toLong(s);
        return v == null || v <= 0 ? fallback : v;
    }
}

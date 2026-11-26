package com.qabulls.appkium.agent;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.Charset;

/**
 * 기기 안에서 파일을 읽고 명령을 실행한다.
 *
 * shell 권한으로 돌기 때문에 adb shell 에서 읽던 /proc · sysfs 를 그대로 읽을 수 있다(권한이 늘지는 않는다).
 * 실패하면 예외 대신 null 을 돌려준다 — 표본 루프는 값 하나를 못 읽어도 계속 돌아야 한다.
 */
final class Sys implements Device {
    static final Sys INSTANCE = new Sys();
    private static final Charset UTF8 = Charset.forName("UTF-8");

    private Sys() {}

    @Override public String read(String path) {
        try {
            InputStream in = new FileInputStream(path);
            try {
                return new String(readAll(in), UTF8);
            } finally {
                in.close();
            }
        } catch (IOException | SecurityException e) {
            return null;
        }
    }

    @Override public String[] list(String dir) {
        try {
            return new File(dir).list();
        } catch (SecurityException e) {
            return null;
        }
    }

    /**
     * 명령을 실행해 표준 출력을 받는다. 표준 오류는 버린다. [timeoutMs] 가 지나면 끝내고 null.
     * Process.waitFor(timeout) 은 Android 8 부터라 읽기 스레드 join 으로 시간을 잰다.
     */
    @Override public String exec(long timeoutMs, String... cmd) {
        final Process p;
        try {
            p = new ProcessBuilder(cmd).start();
        } catch (IOException e) {
            return null;
        }
        final ByteArrayOutputStream out = new ByteArrayOutputStream(8192);
        Thread reader = new Thread(new Runnable() {
            @Override public void run() {
                try { out.write(readAll(p.getInputStream())); } catch (IOException ignored) { }
            }
        }, "exec-out");
        Thread drain = new Thread(new Runnable() {
            @Override public void run() {
                try { readAll(p.getErrorStream()); } catch (IOException ignored) { }
            }
        }, "exec-err");
        reader.setDaemon(true);
        drain.setDaemon(true);
        reader.start();
        drain.start();
        try {
            reader.join(timeoutMs);
        } catch (InterruptedException e) {
            p.destroy();
            Thread.currentThread().interrupt();
            return null;
        }
        if (reader.isAlive()) {
            p.destroy();
            return null;
        }
        try {
            p.waitFor();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
        return new String(out.toByteArray(), UTF8);
    }

    private static byte[] readAll(InputStream in) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream(4096);
        byte[] buf = new byte[8192];
        int n;
        while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
        return out.toByteArray();
    }
}

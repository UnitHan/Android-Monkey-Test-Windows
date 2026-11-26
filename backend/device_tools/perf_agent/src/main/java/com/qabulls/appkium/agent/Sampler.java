package com.qabulls.appkium.agent;

import java.util.Collections;
import java.util.Map;

/**
 * 대상 앱 한 개의 표본 1회를 만든다 (PC 쪽 PerfMonitor 의 tick 과 같은 계산).
 *
 * CPU · 네트워크는 직전 표본과의 차이로 내므로 상태를 갖는다. PSS 와 기기 온도는 느린 dumpsys 라
 * [refreshSlow] 를 별도 스레드에서 5초마다 불러 갱신하고, 표본에는 마지막 값을 싣는다.
 */
final class Sampler {
    private static final long EXEC_TIMEOUT_MS = 4_000L;
    private static final long SLOW_TIMEOUT_MS = 10_000L;

    private final Device device;
    private final String packageName;
    private final Frames frames;

    private volatile int pid = -1;
    private long lastProcessCpu = -1L;
    private long lastTotalCpu = -1L;
    private long lastDeviceTotal = -1L;
    private long lastDeviceIdle = -1L;
    private long[] lastNet;
    private long lastNetAtMs;
    private int notRunningStreak;

    private volatile Long latestPssKb;
    /** 메모리 세부(KB): java · native · graphics · code · other. 없으면 빈 맵. */
    private volatile Map<String, Float> latestMemDetail = Collections.emptyMap();
    private volatile Map<String, Float> latestThermal = Collections.emptyMap();
    /** 열 상태(0~6). thermalservice 가 없는 Android 9 이하는 null. */
    private volatile Integer latestThermalStatus;

    Sampler(Device device, String packageName) {
        this.device = device;
        this.packageName = packageName;
        this.frames = new Frames(device, packageName);
    }

    /** [nowMs] 는 기기의 단조 시계(ms). 비율 계산의 경과 시간에만 쓴다. */
    Json tick(long nowMs) {
        long started = System.nanoTime();
        int p = findPid();
        boolean running = p > 0;
        if (!running) {
            notRunningStreak++;
            lastProcessCpu = -1L;
        } else {
            notRunningStreak = 0;
        }
        if (running && frames.layer() == null) frames.ensureLayer(nowMs);

        String procStat = device.read("/proc/stat");
        long[] total = Parse.totalCpu(procStat);
        int cores = Parse.coreCount(procStat);

        Long pcpu = null, rssKb = null, threads = null;
        Integer adj = null;
        if (running) {
            pcpu = Parse.processCpu(device.read("/proc/" + p + "/stat"));
            String status = device.read("/proc/" + p + "/status");
            rssKb = Parse.statusValue(status, "VmRSS:");
            threads = Parse.statusValue(status, "Threads:");
            adj = Parse.toInt(device.readTrim("/proc/" + p + "/oom_score_adj"));
            // 읽는 사이 앱이 끝났으면 실행 중이 아닌 것으로 본다.
            if (pcpu == null && rssKb == null) running = false;
        }

        Float appCpu = cpuPercent(pcpu, total);
        Float sysCpu = deviceCpuPercent(total);
        Integer freqMax = cpuFreqMaxMhz(cores);
        float[] net = netRate(Parse.netBytes(device.read("/proc/net/dev")), nowMs);
        String batteryText = device.exec(EXEC_TIMEOUT_MS, "dumpsys", "battery");
        Long sysfsCurrent = Parse.toLong(device.readTrim("/sys/class/power_supply/battery/current_now"));
        Parse.Battery battery = Parse.battery(batteryText, sysfsCurrent,
            sysfsCurrent == null ? serviceCurrentMicroAmps() : null);
        Frames.Result frame = running ? frames.sample(nowMs) : null;
        Map<String, Float> temps = latestThermal;

        Json battJson = new Json()
            .put("level", battery.level)
            .put("tempC", battery.tempC)
            .put("voltageV", battery.voltageV)
            .put("currentMa", battery.currentMa)
            .put("charging", battery.charging);

        return Json.type("sample")
            .put("running", running)
            .put("foreground", adj != null && adj <= 0)
            .put("pid", running ? Integer.valueOf(p) : null)
            .put("fps", frame == null ? null : frame.fps)
            .put("jank", frame == null ? null : frame.jankCount)
            .put("frameMaxMs", frame == null ? null : frame.frameTimeMaxMs)
            .put("layer", frame == null ? null : frame.layer)
            .put("appCpu", appCpu)
            .put("cores", cores > 0 ? Integer.valueOf(cores) : null)
            .put("sysCpu", sysCpu)
            .put("freqMaxMhz", freqMax)
            .put("rssKb", rssKb)
            .put("pssKb", running ? latestPssKb : null)
            .put("memKb", running && !latestMemDetail.isEmpty() ? latestMemDetail : null)
            .put("thermalStatus", latestThermalStatus)
            .put("threads", threads)
            .put("battery", battJson)
            .put("temps", temps)
            .put("netRxKBps", net == null ? null : Float.valueOf(net[0]))
            .put("netTxKBps", net == null ? null : Float.valueOf(net[1]))
            .put("costMs", (System.nanoTime() - started) / 1_000_000L);
    }

    /** PSS 와 기기 온도를 갱신한다. 별도 스레드에서 부른다. */
    void refreshSlow() {
        int p = pid;
        if (p > 0) {
            String meminfo = device.exec(SLOW_TIMEOUT_MS, "dumpsys", "meminfo", packageName);
            latestPssKb = Parse.pssKb(meminfo);
            latestMemDetail = Collections.unmodifiableMap(Parse.memDetailKb(meminfo));
        } else {
            latestPssKb = null;
            latestMemDetail = Collections.emptyMap();
        }
        latestThermal = Collections.unmodifiableMap(readThermal());
    }

    /** 온도를 thermalservice 에서 못 얻는 기기(Android 9 이하 등)인지. 한 번 확인하면 다음부터 바로 대체 경로를 쓴다. */
    private volatile boolean thermalServiceEmpty;

    /** 기기 온도. thermalservice(Android 10+) 가 비면 hardware_properties(Android 7+) 를 쓴다. */
    private Map<String, Float> readThermal() {
        if (!thermalServiceEmpty) {
            String text = device.exec(SLOW_TIMEOUT_MS, "dumpsys", "thermalservice");
            latestThermalStatus = Parse.thermalStatus(text);
            Map<String, Float> t = Parse.thermal(text);
            if (!t.isEmpty()) return t;
            // 열 상태만 있고 HAL 온도가 비는 기기는 상태를 계속 읽어야 하므로 thermalservice 를 계속 쓴다.
            if (latestThermalStatus == null) thermalServiceEmpty = true;
        }
        return Parse.hardwareTemps(device.exec(SLOW_TIMEOUT_MS, "dumpsys", "hardware_properties"));
    }

    /**
     * 대상 앱의 주 프로세스 pid. 직전 pid 의 cmdline 이 그대로면 다시 찾지 않는다.
     * 앱이 꺼져 있을 때 /proc 전체를 매초 훑지 않도록, 연속으로 못 찾으면 3초에 한 번만 찾는다.
     */
    private int findPid() {
        int cached = pid;
        if (cached > 0 && packageName.equals(cmdline(cached))) return cached;
        pid = -1;
        if (notRunningStreak > 3 && notRunningStreak % 3 != 0) return -1;
        String[] names = device.list("/proc");
        if (names != null) {
            for (String n : names) {
                if (n.isEmpty() || !Character.isDigit(n.charAt(0))) continue;
                int candidate;
                try { candidate = Integer.parseInt(n); } catch (NumberFormatException e) { continue; }
                if (packageName.equals(cmdline(candidate))) { pid = candidate; return candidate; }
            }
            return -1;
        }
        Integer viaPidof = Parse.toInt(firstToken(device.exec(EXEC_TIMEOUT_MS, "pidof", "-s", packageName)));
        if (viaPidof != null && viaPidof > 0) pid = viaPidof;
        return pid;
    }

    /** /proc/<pid>/cmdline 의 첫 인자(프로세스 이름). */
    private String cmdline(int p) {
        String s = device.read("/proc/" + p + "/cmdline");
        if (s == null) return null;
        int nul = s.indexOf('\0');
        return (nul >= 0 ? s.substring(0, nul) : s).trim();
    }

    private static String firstToken(String s) {
        if (s == null) return null;
        String t = s.trim();
        int sp = t.indexOf(' ');
        return sp < 0 ? t : t.substring(0, sp);
    }

    /** 기기 전체(모든 코어) 대비 앱 CPU 점유율. 첫 표본은 비교 대상이 없어 null. */
    /** 배터리 서비스로 읽는 전류(BatteryCurrent). Android SDK 로 빌드한 수집기에만 있고, PC 에서 시험할 때는 없다. */
    private static final java.lang.reflect.Method SERVICE_CURRENT = findServiceCurrent();

    private static java.lang.reflect.Method findServiceCurrent() {
        try {
            return Class.forName("com.qabulls.appkium.agent.BatteryCurrent").getMethod("microAmps");
        } catch (Throwable t) {
            return null;
        }
    }

    /** sysfs 를 못 읽는 기기에서만 부른다. 읽지 못하면 null. */
    private static Long serviceCurrentMicroAmps() {
        if (SERVICE_CURRENT == null) return null;
        try {
            return (Long) SERVICE_CURRENT.invoke(null);
        } catch (Throwable t) {
            return null;
        }
    }

    private Float cpuPercent(Long p, long[] total) {
        if (p == null || total == null) return null;
        Float percent = null;
        if (lastProcessCpu >= 0 && lastTotalCpu >= 0) {
            long dp = p - lastProcessCpu;
            long dt = total[0] - lastTotalCpu;
            if (dp >= 0 && dt > 0) percent = dp * 100f / dt;
        }
        lastProcessCpu = p;
        lastTotalCpu = total[0];
        return percent;
    }

    /** 기기 전체 CPU 사용률 = (전체 - idle) 증가분 ÷ 전체 증가분. */
    private Float deviceCpuPercent(long[] total) {
        if (total == null || total[1] < 0) return null;
        Float percent = null;
        if (lastDeviceTotal >= 0 && lastDeviceIdle >= 0) {
            long dt = total[0] - lastDeviceTotal;
            long di = total[1] - lastDeviceIdle;
            if (dt > 0 && di >= 0 && di <= dt) percent = (dt - di) * 100f / dt;
        }
        lastDeviceTotal = total[0];
        lastDeviceIdle = total[1];
        return percent;
    }

    private Integer cpuFreqMaxMhz(int cores) {
        long max = -1;
        for (int i = 0; i < Math.max(cores, 1); i++) {
            Long khz = Parse.toLong(device.readTrim("/sys/devices/system/cpu/cpu" + i + "/cpufreq/scaling_cur_freq"));
            if (khz != null && khz > max) max = khz;
        }
        return max > 0 ? Integer.valueOf((int) (max / 1000)) : null;
    }

    /** 직전 표본과의 바이트 차이로 {수신, 송신} KB/s. 합계가 줄면(인터페이스 사라짐) null. */
    private float[] netRate(long[] bytes, long nowMs) {
        if (bytes == null) return null;
        long[] prev = lastNet;
        long prevAt = lastNetAtMs;
        lastNet = bytes;
        lastNetAtMs = nowMs;
        if (prev == null) return null;
        float sec = (nowMs - prevAt) / 1000f;
        long dr = bytes[0] - prev[0];
        long dtx = bytes[1] - prev[1];
        if (sec <= 0f || dr < 0 || dtx < 0) return null;
        return new float[]{dr / 1024f / sec, dtx / 1024f / sec};
    }
}

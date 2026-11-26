package com.qabulls.appkium.agent;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 기기 출력 해석. PC 쪽 SampleParser · FrameProbe 와 같은 규칙이다 — 둘을 바꿀 때는 함께 바꾼다.
 * 기기 없이 시험할 수 있도록 입출력 없는 함수만 둔다.
 */
final class Parse {
    private Parse() {}

    private static final Pattern WS = Pattern.compile("\\s+");

    /** /proc/stat 첫 줄 → {전체 jiffies, idle + iowait}. 읽지 못하면 null. */
    static long[] totalCpu(String procStat) {
        if (procStat == null) return null;
        int nl = procStat.indexOf('\n');
        String line = (nl < 0 ? procStat : procStat.substring(0, nl)).trim();
        if (!line.startsWith("cpu ")) return null;
        String[] f = WS.split(line.substring(3).trim());
        long total = 0;
        long[] v = new long[f.length];
        int n = 0;
        for (String s : f) {
            try { v[n] = Long.parseLong(s); total += v[n]; n++; } catch (NumberFormatException ignored) { }
        }
        if (n == 0) return null;
        // user nice system idle iowait … — idle(4번째) + iowait(5번째)
        long idle = n > 3 ? v[3] + (n > 4 ? v[4] : 0) : -1;
        return new long[]{total, idle};
    }

    /** /proc/stat 의 cpuN 줄 수. */
    static int coreCount(String procStat) {
        if (procStat == null) return 0;
        int n = 0;
        for (String line : procStat.split("\n")) {
            if (line.length() > 3 && line.startsWith("cpu") && Character.isDigit(line.charAt(3))) n++;
        }
        return n;
    }

    /**
     * /proc/<pid>/stat 의 utime(14) + stime(15).
     * 두 번째 필드 "(프로세스 이름)" 에 공백 · 괄호가 섞일 수 있어 마지막 ')' 뒤부터 센다.
     */
    static Long processCpu(String stat) {
        if (stat == null) return null;
        int close = stat.lastIndexOf(") ");
        if (close < 0) return null;
        String[] f = stat.substring(close + 2).trim().split(" ");
        if (f.length < 13) return null;
        try {
            return Long.parseLong(f[11]) + Long.parseLong(f[12]);
        } catch (NumberFormatException e) {
            return null;
        }
    }

    /** /proc/<pid>/status 의 "Key:  123 kB" 값. */
    static Long statusValue(String status, String key) {
        if (status == null) return null;
        for (String line : status.split("\n")) {
            if (!line.startsWith(key)) continue;
            String v = line.substring(key.length()).trim();
            if (v.endsWith("kB")) v = v.substring(0, v.length() - 2).trim();
            try { return Long.parseLong(v); } catch (NumberFormatException e) { return null; }
        }
        return null;
    }

    static Integer toInt(String s) {
        if (s == null) return null;
        try { return Integer.parseInt(s.trim()); } catch (NumberFormatException e) { return null; }
    }

    static Long toLong(String s) {
        if (s == null) return null;
        try { return Long.parseLong(s.trim()); } catch (NumberFormatException e) { return null; }
    }

    /** /proc/net/dev 에서 lo 를 뺀 {수신, 송신} 바이트 합계. 인터페이스가 없으면 null. */
    static long[] netBytes(String text) {
        if (text == null) return null;
        long rx = 0, tx = 0;
        boolean found = false;
        for (String line : text.split("\n")) {
            int colon = line.indexOf(':');
            if (colon < 0) continue;
            String name = line.substring(0, colon).trim();
            if (name.isEmpty() || name.equals("lo") || name.contains(" ") || name.contains("|")) continue;
            String[] f = WS.split(line.substring(colon + 1).trim());
            if (f.length < 9) continue;
            try {
                long r = Long.parseLong(f[0]);
                long t = Long.parseLong(f[8]);
                rx += r;
                tx += t;
                found = true;
            } catch (NumberFormatException ignored) { }
        }
        return found ? new long[]{rx, tx} : null;
    }

    static final class Battery {
        final Integer level;
        final Float tempC;
        final Float voltageV;
        final Float currentMa;
        final Boolean charging;

        Battery(Integer level, Float tempC, Float voltageV, Float currentMa, Boolean charging) {
            this.level = level;
            this.tempC = tempC;
            this.voltageV = voltageV;
            this.currentMa = currentMa;
            this.charging = charging;
        }
    }

    private static Integer batteryInt(String text, String key) {
        Matcher m = Pattern.compile("(?m)^\\s*" + Pattern.quote(key) + ":\\s*(-?\\d+)").matcher(text);
        return m.find() ? toInt(m.group(1)) : null;
    }

    /**
     * `dumpsys battery`. status 2 충전 중 · 5 완충, voltage mV, temperature 0.1°C, current now mA(일부 기기만).
     * 전류가 dumpsys 에 없으면 sysfs current_now 를 쓴다.
     */
    static Battery battery(String text, Long sysfsCurrentRaw) {
        return battery(text, sysfsCurrentRaw, null);
    }

    /**
     * 전류는 dumpsys 의 "current now", sysfs current_now, 배터리 서비스 값([serviceMicroAmps], µA) 순으로 쓴다.
     * 서비스 값은 단위가 정해져 있어 sysfs 처럼 크기로 단위를 짐작하지 않는다.
     */
    static Battery battery(String text, Long sysfsCurrentRaw, Long serviceMicroAmps) {
        if (text == null) text = "";
        Integer level = batteryInt(text, "level");
        Integer temp = batteryInt(text, "temperature");
        Integer voltage = batteryInt(text, "voltage");
        Integer current = batteryInt(text, "current now");
        Integer status = batteryInt(text, "status");
        return new Battery(
            level,
            temp == null ? null : temp / 10f,
            voltage == null ? null : voltageV(voltage.longValue()),
            current != null ? Float.valueOf(current.floatValue())
                : sysfsCurrentRaw != null ? currentMa(sysfsCurrentRaw)
                : serviceMicroAmps != null ? Float.valueOf(serviceMicroAmps / 1000f) : null,
            status == null ? null : (status == 2 || status == 5));
    }

    /** current_now 를 mA 로. 절댓값이 10,000 을 넘으면 µA 로 본다. */
    static Float currentMa(Long raw) {
        if (raw == null) return null;
        if (raw == 0L) return 0f;
        return Math.abs(raw) > 10_000 ? raw / 1000f : raw.floatValue();
    }

    /** 전압을 V 로. sysfs 는 대부분 µV, dumpsys 는 mV. */
    static Float voltageV(Long raw) {
        if (raw == null || raw <= 0L) return null;
        if (raw > 100_000) return raw / 1_000_000f;
        if (raw > 1_000) return raw / 1_000f;
        return raw.floatValue();
    }

    /** dumpsys meminfo 의 총 PSS(KB). "TOTAL PSS:" 또는 "TOTAL" 표 줄. */
    static Long pssKb(String meminfo) {
        if (meminfo == null) return null;
        Matcher m = Pattern.compile("TOTAL PSS:\\s*(\\d+)").matcher(meminfo);
        if (m.find()) return toLong(m.group(1));
        m = Pattern.compile("(?m)^\\s*TOTAL\\s+(\\d+)").matcher(meminfo);
        if (m.find()) return toLong(m.group(1));
        return null;
    }

    /** `dumpsys thermalservice` 의 "Current temperatures from HAL" 아래 이름별 온도. 0 은 뺀다. */
    static Map<String, Float> thermal(String text) {
        Map<String, Float> out = new LinkedHashMap<>();
        if (text == null) return out;
        String block = text;
        int a = block.indexOf("Current temperatures from HAL");
        if (a >= 0) block = block.substring(a);
        int b = block.indexOf("Current cooling devices");
        if (b >= 0) block = block.substring(0, b);
        Matcher m = Pattern.compile("mValue=(-?[\\d.]+),\\s*mType=\\d+,\\s*mName=([\\w-]+)").matcher(block);
        while (m.find()) {
            try {
                float v = Float.parseFloat(m.group(1));
                if (v != 0f) out.put(m.group(2), v);
            } catch (NumberFormatException ignored) { }
        }
        return out;
    }

    /**
     * `dumpsys meminfo <패키지>` 의 App Summary(PSS 열, KB). Android 10+ 는 PSS · RSS 두 열이라 첫 숫자를 쓴다.
     * Stack · Private Other · System 은 합쳐 other 로 둔다.
     *
     *     Java Heap:    19492       →  java
     *     Native Heap:    62016     →  native
     *     Code / Graphics           →  code / graphics
     */
    static Map<String, Float> memDetailKb(String meminfo) {
        Map<String, Float> out = new LinkedHashMap<>();
        if (meminfo == null) return out;
        int a = meminfo.indexOf("App Summary");
        if (a < 0) return out;
        String block = meminfo.substring(a);
        String[][] rows = {{"Java Heap", "java"}, {"Native Heap", "native"}, {"Graphics", "graphics"}, {"Code", "code"}};
        for (String[] r : rows) {
            Long v = summaryValue(block, r[0]);
            if (v != null) out.put(r[1], v.floatValue());
        }
        long other = 0;
        boolean any = false;
        for (String name : new String[]{"Stack", "Private Other", "System"}) {
            Long v = summaryValue(block, name);
            if (v != null) { other += v; any = true; }
        }
        if (any) out.put("other", (float) other);
        return out;
    }

    private static Long summaryValue(String block, String name) {
        Matcher m = Pattern.compile("(?m)^\\s*" + Pattern.quote(name) + ":\\s+(\\d+)").matcher(block);
        return m.find() ? toLong(m.group(1)) : null;
    }

    /** `dumpsys thermalservice` 의 "Thermal Status: N" (0~6). Android 10 이상에만 있다. */
    static Integer thermalStatus(String text) {
        if (text == null) return null;
        Matcher m = Pattern.compile("Thermal Status:\\s*(\\d+)").matcher(text);
        return m.find() ? toInt(m.group(1)) : null;
    }

    /**
     * `dumpsys hardware_properties`(Android 7+) 의 온도. thermalservice 가 없는 Android 9 이하나 HAL 온도가 비어 있는 기기용.
     * CPU 는 코어 중 가장 뜨거운 값, 나머지는 첫 값. 정의되지 않은 값(-3.4E38)과 0 은 뺀다.
     * CPU · GPU 는 다이 온도라 부하 때 60°C 넘게 오르므로 칩(AP) 온도 칸에 쓰지 않도록 HW_ 를 붙인다.
     *
     *     CPU temperatures: [39.9, 38.6, …]   →  HW_CPU
     *     GPU temperatures: [36.6]            →  HW_GPU
     *     Battery temperatures: [31.6]        →  BATTERY
     *     Skin temperatures: [36.51]          →  SKIN
     */
    static Map<String, Float> hardwareTemps(String text) {
        Map<String, Float> out = new LinkedHashMap<>();
        if (text == null) return out;
        String[][] names = {{"CPU", "HW_CPU"}, {"GPU", "HW_GPU"}, {"Battery", "BATTERY"}, {"Skin", "SKIN"}};
        for (String[] n : names) {
            Matcher m = Pattern.compile("(?m)^\\s*" + n[0] + " temperatures:\\s*\\[([^\\]]*)]").matcher(text);
            if (!m.find()) continue;
            Float best = null;
            for (String part : m.group(1).split(",")) {
                try {
                    float v = Float.parseFloat(part.trim());
                    if (v == 0f || v < -50f || v > 200f) continue;
                    if (best == null || v > best) best = v;
                    if (!n[0].equals("CPU")) break;
                } catch (NumberFormatException ignored) { }
            }
            if (best != null) out.put(n[1], Math.round(best * 10f) / 10f);
        }
        return out;
    }

    static final class Latency {
        final long refreshPeriodNs;
        final List<Long> presentNs;

        Latency(long refreshPeriodNs, List<Long> presentNs) {
            this.refreshPeriodNs = refreshPeriodNs;
            this.presentNs = presentNs;
        }
    }

    /** 아직 표시되지 않은 프레임은 INT64_MAX 로 나온다. */
    private static final long PENDING = Long.MAX_VALUE;

    /** `dumpsys SurfaceFlinger --latency` → 주사 주기 · 실제 표시 시각(2열) 목록. */
    static Latency latency(String output) {
        if (output == null) return null;
        List<String> lines = new ArrayList<>();
        for (String l : output.split("\n")) {
            String t = l.trim();
            if (!t.isEmpty()) lines.add(t);
        }
        if (lines.isEmpty()) return null;
        Long refresh = toLong(lines.get(0));
        if (refresh == null) return null;
        List<Long> present = new ArrayList<>();
        for (int i = 1; i < lines.size(); i++) {
            String[] cols = WS.split(lines.get(i));
            if (cols.length < 3) continue;
            Long v = toLong(cols[1]);
            if (v != null && v != 0L && v != PENDING) present.add(v);
        }
        return new Latency(refresh, present);
    }

    /**
     * `--list` 한 줄에서 `--latency` 에 넘길 레이어 이름.
     * Android 16 부터는 `RequestedLayerState{<이름> parentId=… z=…}` 로 감싸서 나온다.
     */
    static String layerName(String line) {
        if (!line.startsWith("RequestedLayerState{")) return line;
        String inner = line.substring("RequestedLayerState{".length());
        if (inner.endsWith("}")) inner = inner.substring(0, inner.length() - 1);
        Matcher m = Pattern.compile(" (parentId|relativeParentId|z)=").matcher(inner);
        return m.find() ? inner.substring(0, m.start()) : inner;
    }

    /** 패키지명을 포함한 레이어 후보. SurfaceView(BLAST) → SurfaceView → Activity 창 순. 보조 레이어는 뺀다. */
    static List<String> candidateLayers(String listOutput, String packageName) {
        LinkedHashSet<String> set = new LinkedHashSet<>();
        if (listOutput != null) {
            for (String raw : listOutput.split("\n")) {
                String name = layerName(raw.trim());
                if (!name.contains(packageName)) continue;
                if (name.contains("Background for") || name.contains("Bounds for")
                    || name.contains("ActivityRecordInputSink") || name.startsWith("ActivityRecord{")) continue;
                set.add(name);
            }
        }
        List<String> out = new ArrayList<>(set);
        Collections.sort(out, new Comparator<String>() {
            private int rank(String s) {
                boolean sv = s.contains("SurfaceView");
                if (sv && s.contains("(BLAST)")) return 0;
                if (sv) return 1;
                if (s.contains("/")) return 2;
                return 3;
            }
            @Override public int compare(String a, String b) {
                return Integer.compare(rank(a), rank(b));
            }
        });
        return out;
    }
}

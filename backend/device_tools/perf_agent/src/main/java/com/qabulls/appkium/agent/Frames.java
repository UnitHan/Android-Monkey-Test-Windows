package com.qabulls.appkium.agent;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * SurfaceFlinger 의 프레임 표시 시각으로 FPS 와 끊김을 잰다 (PC 쪽 FrameProbe 와 같은 규칙).
 *
 * `dumpsys SurfaceFlinger --latency <레이어>` 의 실제 표시 시각(2열)이 직전에 본 값보다 큰 프레임만 새 프레임으로 센다.
 * 주사 주기의 2배를 넘긴 프레임 간격을 끊김으로 센다.
 */
final class Frames {
    static final class Result {
        final Float fps;
        final Integer jankCount;
        final Float frameTimeMaxMs;
        final String layer;

        Result(Float fps, Integer jankCount, Float frameTimeMaxMs, String layer) {
            this.fps = fps;
            this.jankCount = jankCount;
            this.frameTimeMaxMs = frameTimeMaxMs;
            this.layer = layer;
        }
    }

    private static final int MAX_PROBE = 6;
    private static final int REDISCOVER_AFTER_EMPTY = 5;
    private static final long DISCOVER_INTERVAL_MS = 3_000L;
    private static final long TIMEOUT_MS = 4_000L;

    private final Device device;
    private final String packageName;

    private String layer;
    private long lastPresentNs;
    private long lastSampleAtMs;
    private int emptyStreak;
    private long lastDiscoverAtMs = -DISCOVER_INTERVAL_MS;

    Frames(Device device, String packageName) {
        this.device = device;
        this.packageName = packageName;
    }

    String layer() {
        return layer;
    }

    /** 레이어가 없으면 찾는다. 너무 자주 찾지 않도록 3초 간격을 둔다. */
    void ensureLayer(long nowMs) {
        if (layer != null) return;
        if (nowMs - lastDiscoverAtMs < DISCOVER_INTERVAL_MS) return;
        lastDiscoverAtMs = nowMs;
        discover();
    }

    /** 현재 레이어의 latency 를 읽어 직전 호출 이후 구간의 FPS 를 낸다. 레이어가 없으면 null. */
    Result sample(long nowMs) {
        String current = layer;
        if (current == null) return null;
        return onLatency(device.exec(TIMEOUT_MS, "dumpsys", "SurfaceFlinger", "--latency", current), nowMs);
    }

    Result onLatency(String text, long nowMs) {
        String current = layer;
        if (current == null) return null;
        Parse.Latency parsed = Parse.latency(text);
        if (parsed == null) { layer = null; return null; }

        List<Long> newFrames = new ArrayList<>();
        for (Long p : parsed.presentNs) if (p > lastPresentNs) newFrames.add(p);
        Collections.sort(newFrames);
        float elapsedSec = lastSampleAtMs == 0L ? 1f : Math.max((nowMs - lastSampleAtMs) / 1000f, 0.2f);
        // 기준 시각이 없을 때만 첫 호출이다. 프레임이 하나도 없는 정지 화면도 다음 호출부터는 0 FPS 로 잰다.
        boolean firstCall = lastSampleAtMs == 0L;
        lastSampleAtMs = nowMs;
        if (!newFrames.isEmpty()) lastPresentNs = newFrames.get(newFrames.size() - 1);

        // 첫 호출은 기준점만 잡는다. 잰 구간이 없으므로 0 이 아니라 '값 없음'으로 둔다(그래프가 0 으로 떨어져 보이지 않게).
        if (firstCall) return new Result(null, null, null, current);

        // 프레임이 계속 안 올라오면 다른 레이어(예: 화면 전환 후 새 Activity)로 바뀌었을 수 있다.
        if (newFrames.isEmpty()) {
            emptyStreak += 1;
            if (emptyStreak >= REDISCOVER_AFTER_EMPTY) { layer = null; emptyStreak = 0; }
            return new Result(0f, 0, null, current);
        }
        emptyStreak = 0;

        float refreshMs = parsed.refreshPeriodNs / 1_000_000f;
        int jank = 0;
        Float max = null;
        for (int i = 1; i < newFrames.size(); i++) {
            float interval = (newFrames.get(i) - newFrames.get(i - 1)) / 1_000_000f;
            if (refreshMs > 0f && interval > refreshMs * 2f) jank++;
            if (max == null || interval > max) max = interval;
        }
        return new Result(newFrames.size() / elapsedSec, jank, max, current);
    }

    /** 후보 레이어 중 최근 1초 안에 표시된 프레임이 가장 많은 것을 고른다. */
    private void discover() {
        List<String> candidates = Parse.candidateLayers(
            device.exec(TIMEOUT_MS, "dumpsys", "SurfaceFlinger", "--list"), packageName);
        if (candidates.size() > MAX_PROBE) candidates = candidates.subList(0, MAX_PROBE);
        String best = null;
        int bestScore = Integer.MIN_VALUE;
        for (String name : candidates) {
            Parse.Latency l = Parse.latency(device.exec(TIMEOUT_MS, "dumpsys", "SurfaceFlinger", "--latency", name));
            int score;
            if (l == null) score = -1;
            else if (l.presentNs.isEmpty()) score = 0;
            else {
                long newest = Collections.max(l.presentNs);
                score = 0;
                for (Long p : l.presentNs) if (p > newest - 1_000_000_000L) score++;
            }
            if (score > bestScore) { best = name; bestScore = score; }
        }
        if (best == null) return;
        layer = best;
        lastPresentNs = 0L;
        lastSampleAtMs = 0L;
    }
}

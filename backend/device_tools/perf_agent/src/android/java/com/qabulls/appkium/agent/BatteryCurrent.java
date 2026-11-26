package com.qabulls.appkium.agent;

import android.os.BatteryManager;

import java.lang.reflect.Constructor;

/**
 * 배터리 전류를 시스템 배터리 서비스(BatteryManager)로 읽는다.
 *
 * 일부 기기(예: LG Android 9)는 SELinux 가 shell 의 /sys/class/power_supply 읽기를 막고, dumpsys battery 에도
 * 전류가 없다. 배터리 서비스는 health HAL 이 시스템 권한으로 읽은 값을 주므로 이런 기기에서도 나온다.
 * 값은 공식 정의대로 µA 이고, 충전이면 양수 · 방전이면 음수다.
 *
 * Android API 가 필요한 코드라 Android SDK 로 빌드한 수집기에만 있다 — Sampler 는 이 클래스를 이름으로 찾는다.
 */
public final class BatteryCurrent {
    private static BatteryManager manager;
    private static boolean unavailable;

    private BatteryCurrent() {}

    /** 지금 전류(µA). 서비스가 없거나 기기가 값을 주지 않으면 null. */
    public static Long microAmps() {
        if (unavailable) return null;
        try {
            if (manager == null) {
                // Context 가 없는 shell 프로세스라 서비스 이름으로 바로 붙는 생성자를 쓴다.
                Constructor<BatteryManager> c = BatteryManager.class.getDeclaredConstructor();
                c.setAccessible(true);
                manager = c.newInstance();
            }
            long v = manager.getLongProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW);
            return v == Long.MIN_VALUE ? null : Long.valueOf(v);
        } catch (Throwable t) {
            unavailable = true;
            return null;
        }
    }
}

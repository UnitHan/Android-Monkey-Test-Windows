package com.qabulls.appkium.agent;

import android.content.Context;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.drawable.Drawable;
import android.os.Build;
import android.os.Looper;
import android.util.Base64;

import java.io.ByteArrayOutputStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;

/**
 * 앱 아이콘과 이름. 홈 화면이 보여 주는 것과 같게 런처 액티비티의 아이콘 · 이름을 쓰고, 없으면 앱의 것을 쓴다.
 *
 *     app_process / com.qabulls.appkium.agent.Main icons [--size 96] <패키지> …
 *
 * 패키지마다 {"type":"icon","package":…,"version":…,"label":…,"png":"<base64>"} 한 줄,
 * 읽지 못하면 {"type":"icon","package":…,"error":…} 를 쓴다. 끝나면 {"type":"done"}.
 *
 * Android API(android.jar)로 컴파일하므로 Android SDK 가 있을 때만 수집기에 들어간다 — Main 은 이 클래스를 이름으로 찾는다.
 * shell 프로세스에는 Context 가 없어 scrcpy 와 같은 방법으로 시스템 Context 를 만든다.
 */
public final class AppIcons {
    private AppIcons() {}

    public static void main(String[] args) throws Exception {
        int size = 96;
        List<String> packages = new ArrayList<>();
        for (int i = 1; i < args.length; i++) {
            if (args[i].equals("--size") && i + 1 < args.length) size = Math.max(16, Math.min(256, Integer.parseInt(args[++i])));
            else packages.add(args[i]);
        }
        PackageManager pm = systemContext().getPackageManager();
        for (String pkg : packages) {
            try {
                Main.emit(icon(pm, pkg, size));
            } catch (Throwable t) {
                Main.emit(Json.type("icon").put("package", pkg).put("error", String.valueOf(t)));
            }
        }
        Main.emit(Json.type("done"));
    }

    private static Json icon(PackageManager pm, String pkg, int size) throws Exception {
        ApplicationInfo app = pm.getApplicationInfo(pkg, 0);
        Drawable drawable = null;
        CharSequence label = null;
        Intent launch = pm.getLaunchIntentForPackage(pkg);
        ResolveInfo activity = launch == null ? null : pm.resolveActivity(launch, 0);
        if (activity != null) {
            drawable = activity.loadIcon(pm);
            label = activity.loadLabel(pm);
        }
        if (drawable == null) drawable = app.loadIcon(pm);
        if (label == null || label.length() == 0) label = app.loadLabel(pm);
        PackageInfo info = pm.getPackageInfo(pkg, 0);
        @SuppressWarnings("deprecation")
        long version = Build.VERSION.SDK_INT >= 28 ? info.getLongVersionCode() : info.versionCode;
        return Json.type("icon")
            .put("package", pkg)
            .put("version", version)
            .put("label", label == null ? null : label.toString())
            .put("png", png(drawable, size));
    }

    private static String png(Drawable d, int size) {
        Bitmap bitmap = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888);
        d.setBounds(0, 0, size, size);
        d.draw(new Canvas(bitmap));
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        bitmap.compress(Bitmap.CompressFormat.PNG, 100, out);
        bitmap.recycle();
        return Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP);
    }

    /**
     * ActivityThread 를 직접 만들어 시스템 Context 를 얻는다 (scrcpy Workarounds 와 같은 방법).
     * prepareMainLooper 는 API 30 부터 권장하지 않지만(앱은 시스템이 메인 루퍼를 만들어 준다), app_process 로 띄운
     * shell 프로세스에는 메인 루퍼가 없어 직접 만들어야 한다 — 대체 API 가 없어 경고만 끈다.
     */
    @SuppressWarnings("deprecation")
    private static Context systemContext() throws Exception {
        if (Looper.getMainLooper() == null) Looper.prepareMainLooper();
        Class<?> type = Class.forName("android.app.ActivityThread");
        Constructor<?> constructor = type.getDeclaredConstructor();
        constructor.setAccessible(true);
        Object thread = constructor.newInstance();
        Field current = type.getDeclaredField("sCurrentActivityThread");
        current.setAccessible(true);
        current.set(null, thread);
        Field system = type.getDeclaredField("mSystemThread");
        system.setAccessible(true);
        system.setBoolean(thread, true);
        if (Build.VERSION.SDK_INT >= 31) {
            // Android 12 부터는 설정 컨트롤러가 없으면 리소스를 만들 때 멈춘다.
            try {
                Class<?> controllerType = Class.forName("android.app.ConfigurationController");
                Class<?> internal = Class.forName("android.app.ActivityThreadInternal");
                Constructor<?> c = controllerType.getDeclaredConstructor(internal);
                c.setAccessible(true);
                Field f = type.getDeclaredField("mConfigurationController");
                f.setAccessible(true);
                f.set(thread, c.newInstance(thread));
            } catch (Throwable ignored) { }
        }
        Method get = type.getDeclaredMethod("getSystemContext");
        get.setAccessible(true);
        return (Context) get.invoke(thread);
    }
}

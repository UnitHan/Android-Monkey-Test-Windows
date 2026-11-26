import android.content.Context;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.content.res.Resources;
import android.os.Looper;
import android.os.UserHandle;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.drawable.Drawable;
import android.util.Base64;
import java.io.ByteArrayOutputStream;
import org.json.JSONObject;
import org.json.JSONArray;

/** Read installed application labels through Android's own resource resolver. No APK installation. */
public final class AppLabels {
    public static void main(String[] args) throws Exception {
        Looper.prepareMainLooper();
        Class<?> activityThread = Class.forName("android.app.ActivityThread");
        Object thread = activityThread.getMethod("systemMain").invoke(null);
        Context context = (Context) activityThread.getMethod("getSystemContext").invoke(thread);
        int user = (Integer) Class.forName("android.app.ActivityManager")
                .getMethod("getCurrentUser").invoke(null);
        context = (Context) Context.class.getMethod("createContextAsUser", UserHandle.class, int.class)
                .invoke(context, UserHandle.getUserHandleForUid(user * 100000), 0);
        PackageManager pm = context.getPackageManager();
        if (args.length == 2 && "icon".equals(args[0])) {
            System.out.println(icon(pm, args[1]).toString());
            return;
        }
        JSONObject labels = new JSONObject();
        for (ApplicationInfo app : pm.getInstalledApplications(0)) {
            try {
                CharSequence label = pm.getApplicationLabel(app);
                if (label != null && !label.toString().trim().isEmpty()) {
                    labels.put(app.packageName, label.toString());
                }
            } catch (Resources.NotFoundException | SecurityException ignored) {
                // Missing/inaccessible resources fall back to the package identifier on the PC.
            }
        }
        JSONObject result = new JSONObject();
        result.put("version", 1);
        result.put("user", user);
        result.put("locale", context.getResources().getConfiguration().getLocales().toLanguageTags());
        result.put("labels", labels);
        result.put("launchers", launcherLabels(pm));
        System.out.println(result.toString());
    }

    private static JSONObject icon(PackageManager pm, String pkg) throws Exception {
        Drawable drawable = pm.getApplicationIcon(pkg);
        Bitmap bitmap = Bitmap.createBitmap(128, 128, Bitmap.Config.ARGB_8888);
        try {
            drawable.setBounds(0, 0, 128, 128);
            drawable.draw(new Canvas(bitmap));
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            bitmap.compress(Bitmap.CompressFormat.PNG, 100, out);
            JSONObject result = new JSONObject();
            result.put("version", 1);
            result.put("package", pkg);
            result.put("png", Base64.encodeToString(out.toByteArray(), Base64.NO_WRAP));
            return result;
        } finally {
            bitmap.recycle();
        }
    }

    private static JSONObject launcherLabels(PackageManager pm) throws Exception {
        JSONObject result = new JSONObject();
        Intent intent = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        for (ResolveInfo info : pm.queryIntentActivities(intent, 0)) {
            if (info.activityInfo == null) continue;
            String pkg = info.activityInfo.packageName;
            JSONArray labels = result.optJSONArray(pkg);
            if (labels == null) { labels = new JSONArray(); result.put(pkg, labels); }
            try {
                CharSequence label = info.loadLabel(pm);
                if (label != null && !label.toString().trim().isEmpty()) labels.put(label.toString());
            } catch (Resources.NotFoundException | SecurityException ignored) {
                // Keep the launcher package even when its activity label is unavailable.
            }
        }
        return result;
    }
}

package com.qabulls.appkium.agent;

import java.util.Map;

/** 표준 출력에 쓰는 JSON 한 줄을 만든다. 라이브러리를 넣지 않으려고 필요한 만큼만 구현한다. */
final class Json {
    private final StringBuilder sb = new StringBuilder(512).append('{');
    private boolean first = true;

    static Json type(String type) {
        return new Json().put("type", type);
    }

    private StringBuilder key(String k) {
        if (!first) sb.append(',');
        first = false;
        quote(sb, k);
        return sb.append(':');
    }

    Json put(String k, String v) {
        if (v == null) return putNull(k);
        quote(key(k), v);
        return this;
    }

    Json put(String k, Number v) {
        if (v == null) return putNull(k);
        double d = v.doubleValue();
        if (Double.isNaN(d) || Double.isInfinite(d)) return putNull(k);
        key(k);
        if (v instanceof Float || v instanceof Double) {
            // 소수 둘째 자리까지면 화면 · 보고서에 충분하고 줄이 짧아진다.
            sb.append(Math.round(d * 100.0) / 100.0);
        } else {
            sb.append(v.longValue());
        }
        return this;
    }

    Json put(String k, Boolean v) {
        if (v == null) return putNull(k);
        key(k).append(v.booleanValue());
        return this;
    }

    Json put(String k, Json v) {
        if (v == null) return putNull(k);
        key(k).append(v.toString());
        return this;
    }

    Json put(String k, Map<String, Float> v) {
        if (v == null) return putNull(k);
        Json o = new Json();
        for (Map.Entry<String, Float> e : v.entrySet()) o.put(e.getKey(), e.getValue());
        return put(k, o);
    }

    private Json putNull(String k) {
        key(k).append("null");
        return this;
    }

    @Override
    public String toString() {
        return sb.toString() + '}';
    }

    static void quote(StringBuilder sb, String s) {
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < 0x20) sb.append(String.format("\\u%04x", (int) c));
                    else sb.append(c);
            }
        }
        sb.append('"');
    }
}

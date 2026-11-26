package com.qabulls.appkium.agent;

/** 기기 접근. 실제 기기는 [Sys], 시험에서는 가짜 구현을 넣는다. 실패하면 null. */
interface Device {
    String read(String path);

    String[] list(String dir);

    String exec(long timeoutMs, String... cmd);

    default String readTrim(String path) {
        String s = read(path);
        return s == null ? null : s.trim();
    }
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api, type Schemas } from "./client";
import { keys } from "./hooks";

export function usePlayAuthStatus(enabled = true) {
  const qc = useQueryClient();
  const previousPhase = useRef<string>();
  const status = useQuery({
    queryKey: keys.playAuth, queryFn: api.playAuthStatus,
    enabled,
    refetchInterval: (q) => q.state.data?.phase === "pending" ? 1000 : false,
  });
  useEffect(() => {
    if (previousPhase.current === "pending" && status.data?.phase === "connected") {
      void qc.invalidateQueries({ queryKey: ["play"] });
    }
    previousPhase.current = status.data?.phase;
  }, [status.data?.phase, qc]);
  return status;
}

export function usePlayAuth() {
  const qc = useQueryClient();
  const status = usePlayAuthStatus();
  const updated = (value: Schemas["PlayAuthStatus"]) => {
    qc.setQueryData(keys.playAuth, value);
    void qc.invalidateQueries({ queryKey: ["play"] });
  };
  const upload = useMutation({
    mutationFn: async (file: File) => {
      if (file.size > 64_000) throw new Error("클라이언트 JSON 파일은 64KB 이하여야 합니다.");
      return api.configurePlayClient(await file.text());
    }, onSuccess: updated,
  });
  const connect = useMutation({ mutationFn: api.connectPlay, onSuccess: updated });
  const check = useMutation({ mutationFn: api.checkPlay, onSuccess: updated });
  const disconnect = useMutation({ mutationFn: api.disconnectPlay, onSuccess: updated });
  return { status, upload, connect, check, disconnect };
}

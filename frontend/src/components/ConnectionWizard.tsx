/** v3 "ADB 연결 마법사" (400x350, 3 steps) on top of the REST API. */
import { useState } from "react";
import { ApiError, api } from "../api/client";
import { Button, Entry, Radio, Toplevel } from "./tk";

export type Connection = { serial: string; wireless: boolean };
type Status = { text: string; color: "blue" | "orange" | "green" | "red" };

const IDLE: Status = { text: "상태: 대기 중", color: "blue" };
const errText = (e: unknown) => (e instanceof ApiError ? `${e.detail} (request_id ${e.requestId ?? "-"})` : String(e));

export function ConnectionWizard({ onConnected }: { onConnected: (c: Connection) => void }) {
  const [step, setStep] = useState(0);
  const [status0, setStatus0] = useState<Status>(IDLE);
  const [status2, setStatus2] = useState<Status>(IDLE);
  const [usbSerial, setUsbSerial] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const [wireless, setWireless] = useState(false);
  const [ipPort, setIpPort] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  const check = async () => {
    setBusy(true);
    setStatus0({ text: "상태: 연결 확인 중...", color: "orange" });
    try {
      const ready = (await api.devices()).filter((d) => d.state === "device");
      const usb = ready.find((d) => d.connection === "usb") ?? ready[0];
      if (usb) {
        setUsbSerial(usb.serial);
        setWireless(usb.connection === "wifi");
        setStatus0({ text: `상태: 장치 연결됨 (${usb.serial})`, color: "green" });
      } else {
        setUsbSerial(null);
        setWireless(true);
        setStatus0({ text: "상태: 장치 연결 실패. USB 디버깅 및 허용 확인.", color: "red" });
      }
    } catch (e) {
      setStatus0({ text: `상태: 연결 확인 중 오류 발생: ${errText(e)}`, color: "red" });
    } finally {
      setChecked(true);
      setBusy(false);
    }
  };

  const parseTarget = (): { host: string; port: number } | null => {
    const m = /^\s*([A-Za-z0-9.\-]+)(?::(\d{1,5}))?\s*$/.exec(ipPort);
    return m ? { host: m[1], port: m[2] ? Number(m[2]) : 5555 } : null;
  };

  const connectWireless = async () => {
    const target = parseTarget();
    if (!target) return setStatus2({ text: "상태: IP:포트 형식을 확인하세요. 예: 192.168.1.100:5555", color: "red" });
    setBusy(true);
    try {
      if (usbSerial && !usbSerial.includes(":")) {
        setStatus2({ text: "상태: TCP 모드 활성화 중...", color: "orange" });
        await api.tcpip(usbSerial, target.port);
        await new Promise((r) => setTimeout(r, 2000));
      }
      setStatus2({ text: `상태: ${target.host}:${target.port} 연결 시도 중...`, color: "orange" });
      const { serial } = await api.connect(target.host, target.port);
      setStatus2({ text: `상태: ${serial} 연결 성공!`, color: "green" });
      onConnected({ serial, wireless: true });
    } catch (e) {
      setStatus2({ text: `상태: 연결 실패. IP/포트 및 Wi-Fi 확인. ${errText(e)}`, color: "red" });
    } finally {
      setBusy(false);
    }
  };

  const pair = async () => {
    const target = parseTarget();
    if (!target || !/^\d{6}$/.test(code)) {
      return setStatus2({ text: "상태: 페어링 IP:포트와 6자리 코드를 입력하세요.", color: "red" });
    }
    setBusy(true);
    setStatus2({ text: `상태: ${target.host}:${target.port} 페어링 시도 중...`, color: "orange" });
    try {
      await api.pair(target.host, target.port, code);
      setStatus2({ text: `상태: ${target.host}:${target.port} 페어링 성공! 연결 포트로 '무선 연결 시도'를 누르세요.`, color: "green" });
    } catch (e) {
      setStatus2({ text: `상태: 페어링 실패. 코드 또는 IP/포트 확인. ${errText(e)}`, color: "red" });
    } finally {
      setBusy(false);
    }
  };

  const next = () => {
    if (step === 0) return setStep(1);
    if (step === 1 && !wireless && usbSerial) return onConnected({ serial: usbSerial, wireless: false });
    if (step === 1) return setStep(2);
  };

  return (
    <Toplevel title="ADB 연결 마법사" width={460} height={400} opaque>
      <div className="col grow" style={{ gap: 4 }}>
        {step === 0 && (
          <>
            <div className="bold" style={{ fontSize: 15, textAlign: "center", margin: "8px 0" }}>ADB 연결을 시작합니다.</div>
            <div>1. 스마트폰 '개발자 옵션'에서 'USB 디버깅'을 활성화해주세요.</div>
            <div>2. PC와 스마트폰을 USB 케이블로 연결해주세요.</div>
            <div>3. 스마트폰 화면에 뜨는 'USB 디버깅 허용' 팝업에서 '허용'을 눌러주세요.</div>
            <div className={`c-${status0.color}`} style={{ marginTop: 8 }}>{status0.text}</div>
            <div className="row" style={{ justifyContent: "center", marginTop: 6 }}>
              <Button onClick={check} disabled={busy}>ADB 연결 확인</Button>
            </div>
          </>
        )}
        {step === 1 && (
          <>
            <div className="bold" style={{ fontSize: 15, textAlign: "center", margin: "8px 0" }}>어떤 방식으로 연결하시겠습니까?</div>
            <div className="col" style={{ gap: 6, alignItems: "flex-start", paddingLeft: 40 }}>
              <label className="tk-radio" style={{ opacity: usbSerial ? 1 : 0.5 }}>
                <input type="radio" name="mode" checked={!wireless} disabled={!usbSerial} onChange={() => setWireless(false)} />
                유선 (USB 케이블)
              </label>
              <Radio name="mode" checked={wireless} onChange={() => setWireless(true)}>무선 (Wi-Fi)</Radio>
            </div>
          </>
        )}
        {step === 2 && (
          <>
            <div className="bold" style={{ fontSize: 15, textAlign: "center", margin: "4px 0" }}>무선 연결 설정</div>
            <div>1. 스마트폰과 PC가 동일한 Wi-Fi 네트워크에 연결되어 있는지 확인해주세요.</div>
            <div>2. 스마트폰의 IP 주소와 ADB 포트(보통 5555)를 입력해주세요:</div>
            <div>예: 192.168.1.100:5555</div>
            <Entry value={ipPort} onChange={(e) => setIpPort(e.target.value)} placeholder="192.168.1.100:5555" style={{ margin: "4px 0" }} />
            <div className="row" style={{ justifyContent: "center" }}>
              <Button onClick={connectWireless} disabled={busy}>무선 연결 시도</Button>
            </div>
            <div className={`c-${status2.color}`}>{status2.text}</div>
            <div style={{ textAlign: "center", marginTop: 4 }}>Android 11+ 기기: 페어링 코드 입력</div>
            <div className="row" style={{ justifyContent: "center" }}>
              <Entry value={code} onChange={(e) => setCode(e.target.value)} style={{ width: 100 }} inputMode="numeric" />
              <Button onClick={pair} disabled={busy}>페어링 연결</Button>
            </div>
          </>
        )}
      </div>
      <div className="row" style={{ justifyContent: "space-between", marginTop: 8 }}>
        <Button onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0 || busy}>이전</Button>
        <Button onClick={next} disabled={busy || (step === 0 && !checked) || step === 2}>
          {step === 1 && !wireless ? "완료" : "다음"}
        </Button>
      </div>
    </Toplevel>
  );
}

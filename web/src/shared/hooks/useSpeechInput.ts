import { useCallback, useEffect, useRef, useState } from "react";

function getRecognition(): SpeechRecognition | null {
  const w = window as Window & {
    SpeechRecognition?: new () => SpeechRecognition;
    webkitSpeechRecognition?: new () => SpeechRecognition;
  };
  const Ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition;
  return Ctor ? new Ctor() : null;
}

export function useSpeechInput(onTranscript: (chunk: string) => void) {
  const [listening, setListening] = useState(false);
  const [supported, setSupported] = useState(true);
  const recRef = useRef<SpeechRecognition | null>(null);
  const cbRef = useRef(onTranscript);
  cbRef.current = onTranscript;

  useEffect(() => {
    const r = getRecognition();
    if (!r) {
      setSupported(false);
      return;
    }
    recRef.current = r;
    r.lang = navigator.language || "en-US";
    r.continuous = true;
    r.interimResults = false;

    r.onresult = (event: SpeechRecognitionEvent) => {
      let text = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        text += event.results[i]?.[0]?.transcript ?? "";
      }
      const t = text.trim();
      if (t) cbRef.current(t);
    };

    r.onerror = () => {
      setListening(false);
    };

    r.onend = () => {
      setListening(false);
    };

    return () => {
      try {
        r.stop();
      } catch {
        /* noop */
      }
    };
  }, []);

  const toggle = useCallback(() => {
    const r = recRef.current;
    if (!r) return;
    if (listening) {
      try {
        r.stop();
      } catch {
        setListening(false);
      }
      return;
    }
    try {
      r.start();
      setListening(true);
    } catch {
      setListening(false);
    }
  }, [listening]);

  const stop = useCallback(() => {
    const r = recRef.current;
    if (!r || !listening) return;
    try {
      r.stop();
    } catch {
      /* noop */
    }
    setListening(false);
  }, [listening]);

  return { listening, supported, toggle, stop };
}

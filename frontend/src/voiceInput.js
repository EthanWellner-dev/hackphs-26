export function createVoiceInput({ onState, onTranscript, transcribe, scope = globalThis }) {
    let recognition = null, recorder = null, stream = null, timer = null;
    let busy = false, cancelled = false;
    const release = () => { clearTimeout(timer); stream?.getTracks().forEach(track => track.stop()); stream = null; };
    const state = (name, message) => onState(name, message);
    async function record() {
        if (!scope.navigator?.mediaDevices?.getUserMedia || !scope.MediaRecorder) throw new Error('Microphone capture is unavailable. Open this app in Chrome or Edge on localhost.');
        state('requesting', 'Allow microphone access to start recording.');
        stream = await scope.navigator.mediaDevices.getUserMedia({ audio: true });
        if (cancelled) { release(); busy = false; return; }
        const chunks = [];
        recorder = new scope.MediaRecorder(stream);
        recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
        recorder.onerror = () => { release(); busy = false; recorder = null; state('error', 'Recording failed. Check your microphone and retry.'); };
        recorder.onstop = async () => {
            const mimeType = recorder?.mimeType || chunks[0]?.type || 'audio/webm';
            recorder = null; release();
            if (cancelled) { busy = false; return; }
            state('transcribing', 'Transcribing your recording…');
            try {
                const text = await transcribe(new Blob(chunks, { type: mimeType }));
                if (!cancelled) { onTranscript(text); state('idle', 'Transcript ready. Review and send.'); }
            } catch (error) { if (!cancelled) state('error', error.message); }
            finally { busy = false; }
        };
        recorder.start();
        state('listening', 'Recording — speak now. Click the microphone again to finish (maximum 30 seconds).');
        timer = setTimeout(() => recorder?.state === 'recording' && recorder.stop(), 30000);
    }
    return {
        async toggle() {
            if (recorder?.state === 'recording') { recorder.stop(); return; }
            if (recognition) { recognition.stop(); return; }
            if (busy) return;
            busy = true; cancelled = false;
            const Recognition = scope.SpeechRecognition || scope.webkitSpeechRecognition;
            try {
                if (!Recognition) return await record();
                recognition = new Recognition();
                recognition.lang = 'en-US'; recognition.interimResults = true;
                let finalText = '', failed = false;
                recognition.onstart = () => state('listening', 'Listening — speak now. Click the microphone again to finish.');
                recognition.onresult = event => {
                    let partial = '';
                    for (let i = event.resultIndex; i < event.results.length; i++) {
                        if (event.results[i].isFinal) finalText += event.results[i][0].transcript + ' ';
                        else partial += event.results[i][0].transcript;
                    }
                    state('listening', finalText + partial || 'Listening…');
                };
                recognition.onerror = event => {
                    failed = true;
                    state('error', ['not-allowed', 'service-not-allowed'].includes(event.error)
                        ? 'Microphone or speech permission denied. Allow microphone access, or use Record audio below.'
                        : 'Browser speech recognition failed (' + event.error + '). Use Record audio below.');
                };
                recognition.onend = () => {
                    recognition = null; busy = false; clearTimeout(timer);
                    if (cancelled) return;
                    if (finalText.trim()) { onTranscript(finalText.trim()); state('idle', 'Transcript ready. Review and send.'); }
                    else if (!failed) state('error', 'No speech detected. Retry or use Record audio below.');
                };
                state('requesting', 'Waiting for microphone permission…');
                recognition.start();
                timer = setTimeout(() => recognition?.stop(), 30000);
            } catch (error) { recognition = null; busy = false; release(); state('error', error.message); }
        },
        async record() {
            if (busy) return;
            busy = true; cancelled = false;
            try { await record(); }
            catch (error) { busy = false; release(); state('error', error.name === 'NotAllowedError' ? 'Microphone access denied. Enable it in browser/site permissions and retry.' : error.message); }
        },
        cancel() { cancelled = true; recognition?.abort(); if (recorder?.state === 'recording') recorder.stop(); release(); busy = false; state('idle', 'Recording cancelled.'); },
    };
}

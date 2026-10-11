import { describe, expect, it, vi } from 'vitest';
import { createVoiceInput } from './voiceInput.js';

class FakeRecognition {
    start() {
        queueMicrotask(() => {
            this.onerror?.({ error: 'network' });
            this.onend?.();
        });
    }
    stop() { this.onend?.(); }
    abort() { this.onend?.(); }
}

class FakeRecorder {
    constructor() { this.state = 'inactive'; this.mimeType = 'audio/webm'; }
    start() {
        this.state = 'recording';
        this.onstart?.();
    }
    stop() {
        this.state = 'inactive';
        this.ondataavailable?.({ data: new Blob(['audio']) });
        this.onstop?.();
    }
}

describe('createVoiceInput', () => {
    it('falls back to recording when browser speech recognition reports a network error', async () => {
        const states = [];
        const onTranscript = vi.fn();
        const scope = {
            SpeechRecognition: FakeRecognition,
            navigator: { mediaDevices: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [] }) } },
            MediaRecorder: FakeRecorder,
        };
        const voice = createVoiceInput({
            scope,
            onState: (name, message) => states.push({ name, message }),
            onTranscript,
            transcribe: vi.fn().mockResolvedValue('recorded dispatch'),
        });

        await voice.toggle();
        await Promise.resolve();
        expect(states.at(-1).name).toBe('listening');
        expect(states.at(-1).message).toContain('Recording');

        await voice.toggle();
        await Promise.resolve();
        await Promise.resolve();
        expect(onTranscript).toHaveBeenCalledWith('recorded dispatch');
    });
});

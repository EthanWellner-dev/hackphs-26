export class ForecastPlayback {
    constructor({ load, render, status, delay = 550 }) {
        Object.assign(this, { load, render, status, delay });
        this.token = 0;
        this.playing = false;
    }
    stop() {
        this.token++;
        this.playing = false;
        this.status('paused');
    }
    async play(start = 0) {
        this.stop();
        const token = this.token;
        this.playing = true;
        try {
            for (let minute = start; minute <= 120; minute += 5) {
                if (token !== this.token) return;
                this.status('loading', minute);
                const frame = await this.load(minute);
                if (token !== this.token) return;
                if (!frame) { this.stop(); return; }
                this.render(frame);
                this.status('playing', minute);
                if (minute < 120) await new Promise(resolve => setTimeout(resolve, this.delay));
            }
            if (token === this.token) this.stop();
        } catch (error) {
            if (token !== this.token) return;
            this.stop();
            if (error.name !== 'AbortError') this.status('error');
        }
    }
}

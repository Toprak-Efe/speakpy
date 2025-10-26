from .synthesizer import Synthesizer
from .config import APP_NAME, APP_FIFO_NAME 
from .notify import Notifier 

import sounddevice as sd
import numpy as np
from queue import Queue
import threading
import sys
import os
import fcntl
from piper import AudioChunk

import select
from concurrent.futures import ThreadPoolExecutor
from pedalboard import Bitcrush, Distortion, HighpassFilter, PeakFilter, Chorus, Reverb, Delay, Compressor, Limiter 
from pedalboard._pedalboard import Pedalboard

class VoiceServer():
    def __init__(self):
        fifo_folder_path = os.path.join('/var/tmp', APP_NAME)
        fifo_path = os.path.join('/var/tmp', APP_NAME, APP_FIFO_NAME)
        if not os.path.exists(fifo_folder_path):
            sys.exit(1)
        try:
            os.mkfifo(fifo_path)
        except FileExistsError:
            pass

        self._shutdown_r, self._shutdown_w = os.pipe()
        fcntl.fcntl(self._shutdown_r, fcntl.F_SETFL, os.O_NONBLOCK)
        fcntl.fcntl(self._shutdown_w, fcntl.F_SETFL, os.O_NONBLOCK)
        
        self._notifier = Notifier()
        self._synthesizer = Synthesizer()
        self._audio_board = Pedalboard([
            Bitcrush(bit_depth=6),
            Distortion(drive_db=18),
            HighpassFilter(cutoff_frequency_hz=120),
            PeakFilter(cutoff_frequency_hz=150, gain_db=18, q=1.5),
            PeakFilter(cutoff_frequency_hz=80, gain_db=12, q=2),
            PeakFilter(cutoff_frequency_hz=800, gain_db=-12, q=4),
            PeakFilter(cutoff_frequency_hz=1800, gain_db=10, q=3),
            PeakFilter(cutoff_frequency_hz=3200, gain_db=8, q=2.5),
            PeakFilter(cutoff_frequency_hz=5500, gain_db=4, q=1.5),
            Chorus(rate_hz=1.2, depth=0.8, mix=0.3),
            Reverb(room_size=0.6, damping=0.4, wet_level=0.35, dry_level=0.65),
            Delay(delay_seconds=0.05, feedback=0.35, mix=0.25),
            Compressor(threshold_db=-25, ratio=8, attack_ms=2, release_ms=300),
            Limiter(threshold_db=-0.5, release_ms=50),
        ])

        self._fifo = os.open(fifo_path, os.O_RDONLY | os.O_NONBLOCK)
        self._keep_alive_fifo = os.open(fifo_path, os.O_WRONLY | os.O_NONBLOCK)

        self._threads: list[threading.Thread] = []
        self._queue_input_text: Queue[str | None] = Queue()
        self._queue_audio_play: Queue[bytes | None] = Queue()

    def _cleanup(self):
        os.close(self._shutdown_r)
        os.close(self._shutdown_w)
        os.close(self._fifo)

    def _stream_voices(self):
        with sd.RawOutputStream(samplerate=self._synthesizer.get_sample_rate(), channels=1, dtype="int16") as stream:
            while True:
                audio = self._queue_audio_play.get()
                if audio is None:
                    self._queue_audio_play.task_done()
                    break

                self._queue_audio_play.task_done()
                stream.write(audio) 

    def _process_voices(self):
        while True:
            text = self._queue_input_text.get()
            if text is None:
                self._queue_input_text.task_done()
                break

            last_chunk = None
            for chunk in self._synthesizer.synthesize(text, 1.0):
                last_chunk = chunk 
                duration = len(chunk.audio_int16_array)/chunk.sample_rate
                audio_bytes = chunk.audio_int16_bytes
                audio_float = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                effected_float = self._audio_board(audio_float, sample_rate=self._synthesizer.get_sample_rate())
                effected_float = np.clip(effected_float, -2.0, 2.0)
                effected_int16 = (effected_float * 32767.0).astype(np.int16)
                self._notifier.notify(text, duration)
                self._queue_audio_play.put(effected_int16.tobytes())

            if last_chunk is not None:
                tail_duration = 1.5  # seconds
                tail_samples = int(last_chunk.sample_rate * tail_duration)
                silence = np.zeros(tail_samples, dtype=np.float32)
                tail_audio = self._audio_board(silence, sample_rate=last_chunk.sample_rate)
                tail_audio = np.clip(tail_audio, -1.0, 1.0)
                fade_samples = len(tail_audio)
                fade_curve = np.linspace(1.0, 0.0, fade_samples)
                tail_audio = tail_audio * fade_curve
                tail_int16 = (tail_audio * 32767.0).astype(np.int16)
                self._queue_audio_play.put(tail_int16.tobytes())
            self._queue_input_text.task_done()
    
    def run(self):
        self._threads.append(threading.Thread(target=self._stream_voices))
        self._threads.append(threading.Thread(target=self._process_voices))
        for t in self._threads:
            t.start()

        poller = select.poll()
        poller.register(self._fifo, select.POLLIN)
        poller.register(self._shutdown_r, select.POLLIN)

        buffer = b'' 
        running = True
        while running:
            try:
                events = poller.poll()
            except InterruptedError:
                continue

            for fd, _ in events:
                if fd == self._fifo:
                    try:
                        blob = os.read(self._fifo, 1024)
                        if blob:
                            buffer += blob
                            while b"\n" in buffer:
                                line, buffer = buffer.split(b"\n", 1)
                                text = line.decode().strip() 
                                if text != "":
                                    self._queue_input_text.put(text)
                    except BlockingIOError:
                        pass
                elif fd == self._shutdown_r:
                    running = False

        poller.unregister(self._fifo) 
        poller.unregister(self._shutdown_r)
        os.close(self._fifo)
        os.close(self._keep_alive_fifo)
        for t in self._threads:
            t.join()
        self._notifier.shutdown()
         
    def shutdown(self):
        self._queue_audio_play.put(None)
        self._queue_input_text.put(None)
        os.write(self._shutdown_w, b'STOP') 

        

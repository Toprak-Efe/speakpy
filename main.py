from piper import voice
from speakpy.server import VoiceServer 

import signal
    
def main():
    voice_server = VoiceServer() 
    
    def exit(signum, frame):
        voice_server.shutdown()

    signal.signal(signal.SIGINT, exit)
    signal.signal(signal.SIGTERM, exit)

    voice_server.run()

if __name__ == "__main__":
    main()

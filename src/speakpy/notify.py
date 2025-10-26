from .config import PORTRAIT_FILENAME

from queue import Queue
import threading
import subprocess as sp
import time
import os

class Notification:
    contents: str
    duration: float

class Notifier():
    def __init__(self):
        self._current_notification_id = None
        self._portrait_path = os.path.abspath(os.path.join(".", "data", PORTRAIT_FILENAME))
        os.makedirs(os.path.dirname(self._portrait_path), exist_ok=True)

        self._notification_queue: Queue[Notification | None] = Queue()
        self._notification_thread = threading.Thread(target=self._dialogue_notify)
        self._notification_thread.start()

    def _generate_notify_command(self, msg: str, timeout: str, id: str | None = None) -> list[str]:
        cmd = [
            "notify-send",
            "-i", self._portrait_path,
            "-u", "critical",
            "-t", timeout,
            "--print-id", 
        ]
        if id: 
            cmd.extend(["-r", id])
        cmd.extend(["System Alert", msg])
        return cmd

    def _start_notification(self) -> str | None:
        notification_id = None
        try:
            proc = sp.Popen(self._generate_notify_command("", str(1000)), stdout=sp.PIPE, stderr=sp.PIPE, text=True)
            stdout_data, stderr_data = proc.communicate()
            if proc.returncode == 0:
                notification_id = stdout_data.strip()
            else:
                print(f"Error sending notification: {stderr_data}")
        except FileNotFoundError:
            print("Error: 'notify-send' command not found.")
        except Exception as e:
            print(f"An error occurred!: {e}")
        return notification_id 

    def _dialogue_notify(self):
        while True:
            notification = self._notification_queue.get()
            if notification is None:
                break

            character_typing_interval = notification.duration/(len(notification.contents)*3.0)
            notification_id = self._start_notification()
            if notification_id is None:
                continue

            for i in range(len(notification.contents)+1):
                text = notification.contents[:i]
                try:
                    proc = sp.Popen(self._generate_notify_command(text, "5000", notification_id), stdout=sp.PIPE, stderr=sp.PIPE, text=True)
                    stdout_data, stderr_data = proc.communicate()
                    if proc.returncode != 0:
                        print(f"Error sending notification: {stderr_data}")
                except FileNotFoundError:
                    print("Error: 'notify-send' command not found.")
                except Exception as e:
                    print(f"An error occurred: {e}")
                time.sleep(character_typing_interval)

    def shutdown(self):
        self._notification_queue.put(None)
        self._notification_thread.join()

    def notify(self, msg: str, duration: float = 3.0):
        notification = Notification()
        notification.contents = msg
        notification.duration = duration
        self._notification_queue.put(notification)

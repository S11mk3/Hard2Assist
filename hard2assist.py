"""Hard2Assist -- listen for "computer <something>" and do it."""

import pyfiglet
import speech_recognition as sr

import registry

PREFIX = "computer"

# How long to wait for you to start talking, and how long a single command can
# run. Without these, listen() blocks forever and the program looks frozen.
LISTEN_TIMEOUT = 5
PHRASE_LIMIT = 8


def handle(commands, text):
    """Deal with one recognised sentence. Returns registry.STOP to quit."""
    spoken = text.lower().strip()

    # The wake word has to start the sentence, otherwise "I bought a computer
    # yesterday" would set things off.
    if not spoken.startswith(PREFIX):
        return None

    utterance = spoken[len(PREFIX):].strip(" ,.")
    if not utterance:
        return None

    print("Command:", utterance)
    return registry.dispatch(commands, utterance)


def main():
    print(pyfiglet.figlet_format("Hard2Assist"))

    commands = registry.load()
    if not commands:
        print("No commands were loaded, so there is nothing to do.")
        return
    print("Commands:", ", ".join(sorted(commands)))

    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        print("Calibrating for background noise, hold on...")
        recognizer.adjust_for_ambient_noise(source, duration=1)

        print(f"Listening. Say '{PREFIX} help' for what I can do, "
              f"'{PREFIX} stop' to quit.\n")

        while True:
            try:
                audio = recognizer.listen(
                    source,
                    timeout=LISTEN_TIMEOUT,
                    phrase_time_limit=PHRASE_LIMIT,
                )
                text = recognizer.recognize_google(audio)
                print("Heard:", text)

                if handle(commands, text) is registry.STOP:
                    break

            except sr.WaitTimeoutError:
                continue  # nobody said anything, just keep listening
            except sr.UnknownValueError:
                print("I didn't catch that.")
            except sr.RequestError as e:
                print(f"Could not reach the speech service: {e}")
            except Exception as e:
                # One bad command should not end the session.
                print(f"Something went wrong: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting.")

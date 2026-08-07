#importing libriaries that are needed
import speech_recognition as sr
import importlib
import os
import pyfiglet

#defining variables
recognizer = sr.Recognizer()
prefix = "computer"
commands = {}


#COMMAND HANDLER
for subfolder in ["TextCommands", "SystemApps"]:
    folder_path = os.path.join(os.path.dirname(__file__), "commands", subfolder)
    for file in os.listdir(folder_path):
        if file.endswith(".py") and file != "__init__.py":
            module_name = file[:-3]
            try:
                module = importlib.import_module(f"commands.{subfolder}.{module_name}")
                commands[module_name.lower()] = module.run
            except Exception as e:
                print(f"Error loading {module_name}: {e}")

print("Loaded commands:", list(commands.keys()))



start_text = pyfiglet.figlet_format("Hard2Assist")
print(start_text)



#MAIN FUNCTION
with sr.Microphone() as source:
    print("Listening to your commands...")

    while True:
        try:
            audio = recognizer.listen(source)

            if audio == True:
                pass
            

            text = recognizer.recognize_google(audio)

            print("Heard:", text)

            if prefix.lower() in text.lower():

                after_prefix = text.lower().split(prefix.lower(), 1)[1].strip()

                print("HEARD PREFIX")
                print("Command:", after_prefix)

                found = False

                for command, action in commands.items():

                    if command in after_prefix:
                        if command in ["open", "kill", "close"]:
                            app_name = after_prefix.split(command, 1)[1].strip()
                            action(app_name)
                        else:
                            action()
                        found = True
                        break

                if not found:
                    print("Unknown command")

        except sr.UnknownValueError:
            print("I didnt understand you")
        
        except sr.RequestError as e:
            print("Error:", e)

        except KeyboardInterrupt:
            print("Exiting")
            break
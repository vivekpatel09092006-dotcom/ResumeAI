Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\Users\patel\Downloads\ResumeAI_Pro_Complete_New\ResumeAI_Career_Platform"
shell.Run "cmd /c python app.py", 0, False
WScript.Sleep 4000
shell.Run "http://127.0.0.1:5001", 1, False

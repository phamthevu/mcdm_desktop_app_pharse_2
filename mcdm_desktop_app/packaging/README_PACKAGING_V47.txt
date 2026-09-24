Research Studio V4.8 - Windows packaging preparation

1. Activate the same virtual environment used to run the app.
2. Run: packaging\build_windows.bat
3. The script compiles source, runs V4.8 DB/logic stress tests, then builds dist\ResearchStudio.exe.
4. Before distribution, manually test the executable on a clean Windows machine with:
   - MCDM Account login/save/edit/reopen/export
   - Quantitative Free + Account
   - Qualitative Free + Account + follow-ups
   - Merge same research config and block different config
   - Template Save As and result Export naming

V4.8 rule: MCDM has no Free Entry. Quantitative and Qualitative retain Free/Account.

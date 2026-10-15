# Download servers

Primary-user setup includes a Download servers page before Wi-Fi. Its standard Glif item opens the shared Settings page and displays the saved choice: Automatic, Europe only or Canada only. Returning refreshes the summary. Next advances without changing the policy. Secondary-user setup excludes this page.

The page reads through Settings' `DiamaneOSDownloadPolicyClient` module and adds no permissions. If the policy cannot be read, the page says so and uses no network. The inherited `app.grapheneos.setupwizard` package remains unchanged.

Run `python3 -m unittest discover -s tests -p 'test_download_servers.py'` with host JDK/Kotlin compilers. The fixtures use stand-ins for Android and the UI, so they do not test the rendered UI or the Android runtime.

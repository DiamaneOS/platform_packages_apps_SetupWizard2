"""Host Kotlin fixtures for the actual entry/activity sequence, with explicit Android/UI doubles."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = '3982cfc3536620c17b2ec5c3494af0fb2a58a633'
NS = '{http://schemas.android.com/apk/res/android}'
JAVA = {
    'android/os/Bundle.java': 'package android.os; public class Bundle {}',
    'android/os/UserManager.java': 'package android.os; public class UserManager { public boolean primary=true; public boolean isSystemUser(){return primary;} }',
    'android/view/View.java': 'package android.view; public class View { private static int next=1; public static int generateViewId(){return next++;} }',
    'android/content/ActivityNotFoundException.java': 'package android.content; public class ActivityNotFoundException extends RuntimeException {}',
    'android/content/ComponentName.java': 'package android.content; public class ComponentName { public final String pkg,cls; public ComponentName(String p,String c){pkg=p;cls=c;} }',
    'android/content/Intent.java': '''package android.content; public class Intent {
        public Class<?> target; public ComponentName component; public final java.util.Map<String,Object> extras=new java.util.HashMap<>();
        public Intent(String action){} public Intent(Context c,Class<?> cls){target=cls;}
        public Intent setComponent(ComponentName c){component=c;return this;}
        public Intent putExtra(String k,boolean v){extras.put(k,v);return this;}
        public Intent putExtra(String k,String v){extras.put(k,v);return this;} }''',
    'android/content/Context.java': '''package android.content; public class Context {
        public final android.os.UserManager users=new android.os.UserManager();
        public <T> T getSystemService(Class<T> cls){
            if(cls==android.os.UserManager.class)return cls.cast(users);
            if(cls==android.app.StatusBarManager.class)return cls.cast(new android.app.StatusBarManager());
            throw new AssertionError("Unexpected service");} }''',
    'android/app/Activity.java': '''package android.app; public class Activity extends android.content.Context {
        public android.content.Intent launched; public int launchCount; public boolean finished;
        public void startActivity(android.content.Intent i){launched=i;launchCount++;}
        public void startActivity(android.content.Intent i,android.os.Bundle b){startActivity(i);}
        public void finish(){finished=true;} }''',
    'android/app/ActivityOptions.java': '''package android.app; public class ActivityOptions {
        public static ActivityOptions makeCustomAnimation(android.content.Context c,int a,int b){return new ActivityOptions();}
        public android.os.Bundle toBundle(){return new android.os.Bundle();} }''',
    'android/app/StatusBarManager.java': 'package android.app; public class StatusBarManager { public void setDisabledForSetup(boolean v){} }',
    'android/R.java': 'package android; public class R { public static class drawable { public static final int stat_sys_download=1; } }',
    'androidx/annotation/StyleRes.java': 'package androidx.annotation; public @interface StyleRes {}',
    'com/google/android/setupdesign/R.java': '''package com.google.android.setupdesign; public class R {
        public static class anim { public static final int sud_slide_next_in=1,sud_slide_next_out=2; } }''',
    'com/google/android/setupcompat/partnerconfig/PartnerConfigHelper.java': '''package com.google.android.setupcompat.partnerconfig; public class PartnerConfigHelper {
        public static String getSuwDefaultThemeString(android.content.Context c){return "fixture-theme";} }''',
    'com/google/android/setupcompat/util/WizardManagerHelper.java': '''package com.google.android.setupcompat.util; public class WizardManagerHelper {
        public static final String EXTRA_IS_FIRST_RUN="firstRun",EXTRA_IS_SETUP_FLOW="setupFlow",EXTRA_THEME="theme"; }''',
    'com/google/android/setupdesign/util/ThemeHelper.java': '''package com.google.android.setupdesign.util; public class ThemeHelper {
        public static int getSuwDefaultTheme(android.content.Context c){return 1;} }''',
    'de/diamaneos/downloads/DownloadPolicy.java': '''package de.diamaneos.downloads; public class DownloadPolicy {
        public static final String PRIMARY="primary_eu",CANADA="canada"; public final String server; public final boolean fallback;
        public DownloadPolicy(String s,boolean f){server=s;fallback=f;} }''',
    'de/diamaneos/downloads/DownloadPolicyClient.java': '''package de.diamaneos.downloads; public class DownloadPolicyClient {
        public static DownloadPolicy saved=new DownloadPolicy(DownloadPolicy.PRIMARY,false); public static boolean unavailable,untrusted;
        public static int reads,writes;
        public static DownloadPolicy read(android.content.Context c) throws java.io.IOException {
            reads++;if(unavailable)throw new java.io.IOException("Authority unavailable fixture");return saved;}
        public static boolean write(android.content.Context c,DownloadPolicy p){writes++;throw new AssertionError("No wizard writes allowed");}
        public static android.content.Intent settingsIntent(android.content.Context c){if(untrusted)throw new SecurityException("Fixture");
            return new android.content.Intent("de.diamaneos.settings.DOWNLOAD_SERVERS").setComponent(new android.content.ComponentName(
                "com.android.settings","com.android.settings.Settings$DownloadServersActivity"));} }''',
}
UI = '''package com.google.android.setupdesign.items
open class Item { var id=0;var title: CharSequence="";var summary: CharSequence="" }
class ItemGroup { val children=mutableListOf<Item>();fun addChild(item: Item){children+=item} }
class RecyclerItemAdapter(val group: ItemGroup) {
    private var selected: ((Item)->Unit)?=null
    fun setOnItemSelectedListener(listener: (Item)->Unit){selected=listener}
    fun click(index: Int){selected!!(group.children[index])}
}
'''
LAYOUT = '''package com.google.android.setupdesign
class GlifRecyclerLayout { var adapter: com.google.android.setupdesign.items.RecyclerItemAdapter?=null }
'''
BASE_ACTIVITY = '''package app.grapheneos.setupwizard.view.activity
import android.content.Intent
import android.os.Bundle
import android.view.View
import com.google.android.setupdesign.GlifRecyclerLayout

class FixtureButton {
    private var click: ((View)->Unit)?=null
    fun setOnClickListener(value: (View)->Unit){click=value}
    fun performClick(){click!!(View())}
}
abstract class SetupWizardActivity(val layoutResID: Int?=null,val icon: Int?=null,val header: Int?=null,val description: Int?=null): android.app.Activity() {
    val layout=GlifRecyclerLayout()
    val primaryButton=FixtureButton()
    var resultIntent: Intent?=null
    var resultLaunches=0
    var missingSettings=false
    open fun onResume(){}
    abstract fun bindViews()
    abstract fun setupActions()
    fun <T> requireViewById(id: Int): T { @Suppress("UNCHECKED_CAST") return layout as T }
    fun getString(id: Int,vararg values: Any): String = String.format(java.util.Locale.ROOT,FixtureStrings.values[id]!!,*values)
    fun startActivityForResult(intent: Intent){if(missingSettings)throw android.content.ActivityNotFoundException();resultIntent=intent;resultLaunches++}
    protected open fun onActivityResult(code: Int,data: Intent?){}
    fun cancelledReturn(){onActivityResult(0,null)}
    fun create(){bindViews();setupActions()}
}
'''
HARNESS = r'''package de.diamaneos.setup
import app.grapheneos.setupwizard.appContext
import app.grapheneos.setupwizard.R
import app.grapheneos.setupwizard.action.SetupWizard
import app.grapheneos.setupwizard.view.activity.*
import de.diamaneos.downloads.DownloadPolicy
import de.diamaneos.downloads.DownloadPolicyClient

fun main(args: Array<String>) {
    appContext=android.content.Context().also { it.users.primary=args[0]!="secondary" }
    if(args[0]=="secondary") {
        val welcome=WelcomeActivity();SetupWizard.next(welcome)
        check(welcome.launched.target==LocationActivity::class.java)
        val location=LocationActivity();SetupWizard.next(location)
        check(location.launched.target==SecurityActivity::class.java)
        try { SetupWizard.next(android.app.Activity(),DownloadServersActivity::class.java);error("Unexpected secondary step") }
        catch(e: IllegalArgumentException){}
        check(DownloadPolicyClient.reads==0 && DownloadPolicyClient.writes==0)
        return
    }
    val activity=DownloadServersActivity();activity.create()
    val adapter=activity.layout.adapter!!
    val row=adapter.group.children.single()
    when(args[0]) {
        "entry" -> {
            val welcome=WelcomeActivity();SetupWizard.next(welcome)
            check(welcome.launched.target==DownloadServersActivity::class.java)
            check(activity.layoutResID==R.layout.activity_location && activity.icon==android.R.drawable.stat_sys_download)
            activity.onResume()
            check(activity.resultLaunches==0 && activity.launchCount==0)
            check(row.javaClass==com.google.android.setupdesign.items.Item::class.java)
        }
        "click" -> {
            activity.onResume();adapter.click(0)
            check(activity.resultLaunches==1)
            check(activity.resultIntent!!.component.pkg=="com.android.settings")
            check(activity.resultIntent!!.component.cls=="com.android.settings.Settings\$DownloadServersActivity")
            check(activity.resultIntent!!.extras["setupFlow"]==true)
            check(activity.resultIntent!!.extras["theme"]=="fixture-theme")
            check(activity.launchCount==0)
        }
        "summary" -> {
            for(server in listOf("primary_eu","canada")) for(fallback in listOf(false,true)) {
                val saved=DownloadPolicy(server,fallback);DownloadPolicyClient.saved=saved
                activity.onResume()
                val region=if(server=="canada")"Canada" else "Europe (primary)"
                check(row.summary=="$region · Fallback ${if(fallback)"on" else "off"}")
                check(DownloadPolicyClient.saved===saved && activity.resultLaunches==0)
            }
        }
        "return_next" -> {
            activity.onResume();adapter.click(0)
            val saved=DownloadPolicy("canada",false);DownloadPolicyClient.saved=saved
            activity.cancelledReturn();activity.onResume()
            check(row.summary=="Canada · Fallback off")
            check(activity.resultLaunches==1 && !activity.finished && activity.launchCount==0)
            activity.primaryButton.performClick()
            check(activity.launched.target==WifiActivity::class.java)
            check(DownloadPolicyClient.saved===saved)
        }
        "unavailable" -> {
            val saved=DownloadPolicy("canada",false);DownloadPolicyClient.saved=saved
            DownloadPolicyClient.unavailable=true;activity.onResume()
            check(row.summary==activity.getString(R.string.download_servers_unavailable))
            check(activity.resultLaunches==0 && activity.launchCount==0)
            activity.primaryButton.performClick()
            check(activity.launched.target==WifiActivity::class.java && DownloadPolicyClient.saved===saved)
        }
        "launch_refusal" -> {
            activity.onResume();DownloadPolicyClient.untrusted=true;adapter.click(0)
            check(activity.resultLaunches==0 && row.summary==activity.getString(R.string.download_servers_unavailable))
            DownloadPolicyClient.untrusted=false;activity.missingSettings=true;adapter.click(0)
            check(activity.resultLaunches==0 && row.summary==activity.getString(R.string.download_servers_unavailable))
            activity.primaryButton.performClick();check(activity.launched.target==WifiActivity::class.java)
        }
        else -> error("Unknown fixture")
    }
    check(DownloadPolicyClient.writes==0)
}
'''


class DownloadServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='setup-download-host-')
        cls.output = Path(cls.tmp.name)
        cls.jdk = Path(os.environ.get('DOWNLOAD_POLICY_JAVA_HOME', '/Applications/Android Studio.app/Contents/jbr/Contents/Home'))
        cls.kotlin = Path(os.environ.get('DOWNLOAD_POLICY_KOTLIN_HOME', '/Applications/Android Studio.app/Contents/plugins/Kotlin/kotlinc'))
        if not (cls.jdk / 'bin/javac').is_file() or not (cls.kotlin / 'lib/kotlin-compiler.jar').is_file():
            raise RuntimeError('Host JDK and Kotlin compiler required; no Android build is used')
        strings = ET.parse(ROOT / 'res/values/download_servers.xml').getroot()
        string_ids = {item.get('name'): index for index, item in enumerate(strings, 10)}
        fields = ','.join(f'{name}={index}' for name, index in string_ids.items())
        resources = 'package app.grapheneos.setupwizard; public class R { public static class string { public static final int ' + fields + '; } public static class layout { public static final int activity_location=1; } public static class id { public static final int glif_layout=1; } }'
        files = dict(JAVA)
        files['app/grapheneos/setupwizard/R.java'] = resources
        for name, content in files.items():
            path = cls.output / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        result = subprocess.run([str(cls.jdk / 'bin/javac'), '--release', '17', '-d', str(cls.output)] + [str(p) for p in cls.output.rglob('*.java')], capture_output=True, text=True, timeout=30)
        if result.returncode: raise RuntimeError(result.stderr)
        import json
        string_map = ','.join(f'{string_ids[item.get("name")]} to {json.dumps(item.text, ensure_ascii=False).replace(chr(36), chr(92) + chr(36))}' for item in strings)
        fixtures = {'Items.kt': UI, 'Layout.kt': LAYOUT, 'BaseActivity.kt': BASE_ACTIVITY,
                    'Strings.kt': 'package app.grapheneos.setupwizard.view.activity\nobject FixtureStrings { val values=mapOf(' + string_map + ') }',
                    'Harness.kt': HARNESS}
        activities = ['DateTimeActivity','FinishActivity','GesturesActivity','LocationActivity','MigrationActivity','SecurityActivity','UpdaterSecurityPreviewActivity','WelcomeActivity','WifiActivity']
        fixtures['Activities.kt'] = 'package app.grapheneos.setupwizard.view.activity\n' + '\n'.join('class '+name+' : android.app.Activity()' for name in activities)
        for name, content in fixtures.items(): (cls.output / name).write_text(content)
        sources = list(cls.output.glob('*.kt')) + [ROOT / p for p in (
            'java/app/grapheneos/setupwizard/Constants.kt',
            'java/app/grapheneos/setupwizard/action/SetupWizard.kt',
            'java/de/diamaneos/setup/DownloadServersActivity.kt')]
        result = subprocess.run([str(cls.jdk / 'bin/java'), '-cp', str(cls.kotlin / 'lib/*'),
                                 'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler', '-kotlin-home', str(cls.kotlin),
                                 '-jvm-target', '17', '-classpath', str(cls.output), '-d', str(cls.output)]
                                + [str(p) for p in sources], capture_output=True, text=True, timeout=45)
        if result.returncode: raise RuntimeError(result.stderr)

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def scenario(self, name):
        cp = str(self.output) + os.pathsep + str(self.kotlin / 'lib/kotlin-stdlib.jar')
        result = subprocess.run([str(self.jdk / 'bin/java'), '-cp', cp, 'de.diamaneos.setup.HarnessKt', name], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_primary_entry_before_wifi_without_auto_launch(self): self.scenario('entry')
    def test_explicit_item_launch_uses_existing_wizard_result_flow(self): self.scenario('click')
    def test_saved_region_and_fallback_summary(self): self.scenario('summary')
    def test_canceled_return_refresh_and_next_preserve_policy(self): self.scenario('return_next')
    def test_unavailable_does_not_launch_or_reset_and_next_advances(self): self.scenario('unavailable')
    def test_missing_or_untrusted_settings_stays_on_wizard_page(self): self.scenario('launch_refusal')
    def test_secondary_sequence_excludes_entry(self): self.scenario('secondary')

    def test_no_permission_change_and_nonexported_activity(self):
        old = subprocess.run(['git', 'show', BASE + ':AndroidManifest.xml'], cwd=ROOT, check=True, capture_output=True, text=True).stdout
        previous = ET.fromstring(old)
        current = ET.parse(ROOT / 'AndroidManifest.xml').getroot()
        self.assertEqual([dict(p.attrib) for p in previous.findall('uses-permission')], [dict(p.attrib) for p in current.findall('uses-permission')])
        self.assertEqual(current.get('package'), 'app.grapheneos.setupwizard')
        activity = next(p for p in current.findall('application/activity') if p.get(NS + 'name') == 'de.diamaneos.setup.DownloadServersActivity')
        self.assertEqual(activity.get(NS + 'exported'), 'false')
        self.assertFalse(list(activity))
        self.assertIn('"DiamaneOSDownloadPolicyClient"', (ROOT / 'Android.bp').read_text())

    def test_native_row_copy_and_no_network_or_policy_write_code(self):
        text = (ROOT / 'java/de/diamaneos/setup/DownloadServersActivity.kt').read_text()
        for prohibited in ('ProxyActivity', 'DownloadPolicyClient.write', 'openConnection', 'putString'):
            self.assertNotIn(prohibited, text)
        for p in ET.parse(ROOT / 'res/values/download_servers.xml').getroot():
            self.assertLessEqual(len((p.text or '').split()), 45)
        for paragraph in (ROOT / 'DOWNLOAD-SERVERS.md').read_text().split('\n\n'):
            self.assertLessEqual(len(paragraph.split()), 45)


if __name__ == '__main__': unittest.main()

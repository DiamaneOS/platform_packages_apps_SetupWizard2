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
    'android/content/ComponentName.java': 'package android.content; public class ComponentName { public final String pkg,cls; public ComponentName(String p,String c){pkg=p;cls=c;} public String getPackageName(){return pkg;} }',
    'android/content/Intent.java': '''package android.content; public class Intent {
        public static final int FLAG_ACTIVITY_NEW_TASK=0x10000000;
        public Class<?> target; public ComponentName component; public String action,pkg; public int flags; public final java.util.Map<String,Object> extras=new java.util.HashMap<>();
        public Intent(String a){action=a;} public Intent(Context c,Class<?> cls){target=cls;}
        public Intent setComponent(ComponentName c){component=c;return this;}
        public Intent setPackage(String p){pkg=p;return this;}
        public Intent addFlags(int f){flags|=f;return this;}
        public ComponentName resolveActivity(android.content.pm.PackageManager pm){return pm.fixtureResolve(this);}
        public Intent putExtra(String k,boolean v){extras.put(k,v);return this;}
        public Intent putExtra(String k,String v){extras.put(k,v);return this;} }''',
    'android/content/pm/PackageManager.java': '''package android.content.pm; public class PackageManager {
        public android.content.ComponentName resolved; public android.content.Intent queried;
        public android.content.ComponentName fixtureResolve(android.content.Intent i){queried=i;return resolved;} }''',
    'android/util/Log.java': 'package android.util; public class Log { public static int d(String t,String m){return 0;} public static int e(String t,String m,Throwable e){return 0;} }',
    'android/content/Context.java': '''package android.content; public class Context {
        public static final android.content.pm.PackageManager packages=new android.content.pm.PackageManager();
        public final android.os.UserManager users=new android.os.UserManager();
        public Intent launched; public int launchCount;
        public android.content.pm.PackageManager getPackageManager(){return packages;}
        public void startActivity(Intent i){launched=i;launchCount++;}
        public <T> T getSystemService(Class<T> cls){
            if(cls==android.os.UserManager.class)return cls.cast(users);
            if(cls==android.app.StatusBarManager.class)return cls.cast(new android.app.StatusBarManager());
            throw new AssertionError("Unexpected service");} }''',
    'android/app/Activity.java': '''package android.app; public class Activity extends android.content.Context {
        public boolean finished;
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
        public static final String AUTOMATIC="automatic",PRIMARY="primary_eu",CANADA="canada"; public final String mode;
        public DownloadPolicy(String m){mode=m;} }''',
    'de/diamaneos/downloads/DownloadPolicyClient.java': '''package de.diamaneos.downloads; public class DownloadPolicyClient {
        public static DownloadPolicy saved=new DownloadPolicy(DownloadPolicy.AUTOMATIC); public static boolean unavailable,untrusted;
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
    var text=0
    fun setText(context: android.content.Context,id: Int){text=id}
    fun setOnClickListener(value: (View)->Unit){click=value}
    fun performClick(){click!!(View())}
}
abstract class SetupWizardActivity(val layoutResID: Int?=null,val icon: Int?=null,val header: Int?=null,val description: Int?=null): android.app.Activity() {
    val layout=GlifRecyclerLayout()
    val primaryButton=FixtureButton()
    val secondaryButton=FixtureButton()
    var resultIntent: Intent?=null
    var resultLaunches=0
    var missingSettings=false
    open fun onCreate(savedInstanceState: Bundle?){bindViews();setupActions()}
    open fun onResume(){}
    abstract fun bindViews()
    abstract fun setupActions()
    fun <T> requireViewById(id: Int): T { @Suppress("UNCHECKED_CAST") return layout as T }
    fun getString(id: Int,vararg values: Any): String = String.format(java.util.Locale.ROOT,FixtureStrings.values[id]!!,*values)
    fun startActivityForResult(intent: Intent){if(missingSettings)throw android.content.ActivityNotFoundException();resultIntent=intent;resultLaunches++}
    protected open fun onActivityResult(code: Int,data: Intent?){}
    fun cancelledReturn(){onActivityResult(0,null)}
    fun create(){onCreate(null)}
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
        for(step in listOf(DownloadServersActivity::class.java,AuditorActivity::class.java)) {
            try { SetupWizard.next(android.app.Activity(),step);error("Unexpected secondary step") }
            catch(e: IllegalArgumentException){}
        }
        check(DownloadPolicyClient.reads==0 && DownloadPolicyClient.writes==0)
        return
    }
    if(args[0].startsWith("auditor")) { auditor(args[0]);return }
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
            for((mode,text) in listOf("automatic" to "Automatic","primary_eu" to "Europe only","canada" to "Canada only")) {
                val saved=DownloadPolicy(mode);DownloadPolicyClient.saved=saved
                activity.onResume()
                check(row.summary==text)
                check(DownloadPolicyClient.saved===saved && activity.resultLaunches==0)
            }
        }
        "return_next" -> {
            activity.onResume();adapter.click(0)
            val saved=DownloadPolicy("canada");DownloadPolicyClient.saved=saved
            activity.cancelledReturn();activity.onResume()
            check(row.summary=="Canada only")
            check(activity.resultLaunches==1 && !activity.finished && activity.launchCount==0)
            activity.primaryButton.performClick()
            check(activity.launched.target==WifiActivity::class.java)
            check(DownloadPolicyClient.saved===saved)
        }
        "unavailable" -> {
            val saved=DownloadPolicy("canada");DownloadPolicyClient.saved=saved
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

fun auditor(name: String) {
    val packages=appContext.packageManager
    val target=android.content.ComponentName("de.diamaneos.auditor","app.attestation.auditor.AttestationActivity")
    packages.resolved=target
    val step=AuditorActivity();step.create()
    check(packages.queried!!.action=="de.diamaneos.auditor.action.ADD_THIS_PHONE" && packages.queried!!.pkg=="de.diamaneos.auditor")
    when(name) {
        "auditor_sequence" -> {
            val gestures=GesturesActivity();SetupWizard.next(gestures)
            check(gestures.launched.target==AuditorActivity::class.java)
            check(!step.finished && step.launchCount==0)
            check(step.layoutResID==R.layout.activity_migration && step.icon==R.drawable.baseline_verified_user_glif)
            check(step.header==R.string.auditor_title && step.description==R.string.auditor_description)
            check(step.primaryButton.text==R.string.auditor_next && step.secondaryButton.text==R.string.auditor_skip)
            step.secondaryButton.performClick();check(step.launched.target==FinishActivity::class.java)
            step.primaryButton.performClick();check(step.launched.target==FinishActivity::class.java)
            check(appContext.launchCount==0)
        }
        "auditor_missing" -> {
            step.primaryButton.performClick()
            for(resolved in listOf(null,android.content.ComponentName("android","com.android.internal.app.ResolverActivity"))) {
                packages.resolved=resolved
                val hidden=AuditorActivity();hidden.create()
                check(hidden.finished && hidden.launched.target==FinishActivity::class.java)
            }
            packages.resolved=target;AuditorActivity.launchIfChosen(appContext)
            check(appContext.launchCount==0)
        }
        "auditor_choice" -> {
            AuditorActivity.launchIfChosen(appContext)
            step.secondaryButton.performClick();AuditorActivity.launchIfChosen(appContext)
            check(appContext.launchCount==0)
            step.primaryButton.performClick();AuditorActivity.launchIfChosen(appContext)
            val launched=appContext.launched
            check(appContext.launchCount==1 && launched.component===target && launched.pkg=="de.diamaneos.auditor")
            check(launched.action=="de.diamaneos.auditor.action.ADD_THIS_PHONE" && launched.flags==android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
            check(launched.extras.isEmpty())
            AuditorActivity.launchIfChosen(appContext);check(appContext.launchCount==1)
            step.primaryButton.performClick();packages.resolved=null;AuditorActivity.launchIfChosen(appContext)
            packages.resolved=target;AuditorActivity.launchIfChosen(appContext)
            check(appContext.launchCount==1)
        }
        else -> error("Unknown fixture")
    }
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
        strings = [item for name in ('download_servers.xml', 'auditor.xml') for item in ET.parse(ROOT / 'res/values' / name).getroot()]
        string_ids = {item.get('name'): index for index, item in enumerate(strings, 10)}
        fields = ','.join(f'{name}={index}' for name, index in string_ids.items())
        resources = 'package app.grapheneos.setupwizard; public class R { public static class string { public static final int ' + fields + '; } public static class drawable { public static final int baseline_download_glif=1,baseline_verified_user_glif=2; } public static class layout { public static final int activity_location=1,activity_migration=2; } public static class id { public static final int glif_layout=1; } }'
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
            'java/de/diamaneos/setup/DownloadServersActivity.kt',
            'java/de/diamaneos/setup/AuditorActivity.kt')]
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
    def test_saved_choice_summary(self): self.scenario('summary')
    def test_canceled_return_refresh_and_next_preserve_policy(self): self.scenario('return_next')
    def test_unavailable_does_not_launch_or_reset_and_next_advances(self): self.scenario('unavailable')
    def test_missing_or_untrusted_settings_stays_on_wizard_page(self): self.scenario('launch_refusal')
    def test_secondary_sequence_excludes_entry(self): self.scenario('secondary')
    def test_auditor_step_after_gestures_before_finish(self): self.scenario('auditor_sequence')
    def test_auditor_step_hidden_without_auditor(self): self.scenario('auditor_missing')
    def test_auditor_opens_once_and_only_when_chosen(self): self.scenario('auditor_choice')

    def test_auditor_opens_only_after_setup_is_marked_complete(self):
        text = (ROOT / 'java/app/grapheneos/setupwizard/action/FinishActions.kt').read_text()
        launch = text.index('AuditorActivity.launchIfChosen(appContext)')
        for step in ('DEVICE_PROVISIONED, 1', 'USER_SETUP_COMPLETE, 1', 'finishAndRemoveTask()', 'context.finish()'):
            self.assertLess(text.index(step), launch)
        self.assertEqual((ROOT / 'java/de/diamaneos/setup/AuditorActivity.kt').read_text().count('startActivity'), 1)

    def test_no_permission_change_and_nonexported_activity(self):
        old = subprocess.run(['git', 'show', BASE + ':AndroidManifest.xml'], cwd=ROOT, check=True, capture_output=True, text=True).stdout
        previous = ET.fromstring(old)
        current = ET.parse(ROOT / 'AndroidManifest.xml').getroot()
        self.assertEqual([dict(p.attrib) for p in previous.findall('uses-permission')], [dict(p.attrib) for p in current.findall('uses-permission')])
        self.assertEqual(current.get('package'), 'app.grapheneos.setupwizard')
        for name in ('de.diamaneos.setup.DownloadServersActivity', 'de.diamaneos.setup.AuditorActivity'):
            activity = next(p for p in current.findall('application/activity') if p.get(NS + 'name') == name)
            self.assertEqual(activity.get(NS + 'exported'), 'false')
            self.assertFalse(list(activity))
        self.assertEqual([p.get(NS + 'name') for p in current.findall('queries/*')], ['de.diamaneos.auditor'])
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

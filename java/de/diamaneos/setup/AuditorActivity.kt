// SPDX-License-Identifier: Apache-2.0
package de.diamaneos.setup

import android.content.ActivityNotFoundException
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.util.Log
import app.grapheneos.setupwizard.R
import app.grapheneos.setupwizard.action.SetupWizard
import app.grapheneos.setupwizard.view.activity.SetupWizardActivity

class AuditorActivity : SetupWizardActivity(
    R.layout.activity_migration,
    R.drawable.baseline_verified_user_glif,
    R.string.auditor_title,
    R.string.auditor_description
) {
    companion object {
        private const val TAG = "AuditorActivity"
        private const val AUDITOR = "de.diamaneos.auditor"
        private const val ACTION_ADD_THIS_PHONE = "de.diamaneos.auditor.action.ADD_THIS_PHONE"

        // In memory only, so a restarted wizard falls back to not opening Auditor.
        private var openAfterSetup = false

        private fun intent() = Intent(ACTION_ADD_THIS_PHONE).setPackage(AUDITOR)

        private fun resolve(context: Context): ComponentName? =
            intent().resolveActivity(context.packageManager)?.takeIf { it.packageName == AUDITOR }

        // Called by FinishActions once setup is marked complete.
        fun launchIfChosen(context: Context) {
            if (!openAfterSetup) return
            openAfterSetup = false
            if (!SetupWizard.isPrimaryUser) return
            val component = resolve(context) ?: return
            try {
                context.startActivity(
                    intent().setComponent(component).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            } catch (e: ActivityNotFoundException) {
                Log.e(TAG, "launchIfChosen", e)
            } catch (e: SecurityException) {
                Log.e(TAG, "launchIfChosen", e)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (resolve(this) == null) {
            Log.d(TAG, "onCreate: skipping: missing Auditor")
            openAfterSetup = false
            finish()
            SetupWizard.next(this)
        }
    }

    override fun bindViews() {
        primaryButton.setText(this, R.string.auditor_next)
        secondaryButton.setText(this, R.string.auditor_skip)
    }

    override fun setupActions() {
        primaryButton.setOnClickListener { choose(true) }
        secondaryButton.setOnClickListener { choose(false) }
    }

    private fun choose(open: Boolean) {
        openAfterSetup = open
        SetupWizard.next(this)
    }
}

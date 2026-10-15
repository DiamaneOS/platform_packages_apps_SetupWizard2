// SPDX-License-Identifier: Apache-2.0
package de.diamaneos.setup

import android.content.ActivityNotFoundException
import android.view.View
import app.grapheneos.setupwizard.R
import app.grapheneos.setupwizard.action.SetupWizard
import app.grapheneos.setupwizard.view.activity.SetupWizardActivity
import com.google.android.setupdesign.GlifRecyclerLayout
import com.google.android.setupdesign.items.Item
import com.google.android.setupdesign.items.ItemGroup
import com.google.android.setupdesign.items.RecyclerItemAdapter
import de.diamaneos.downloads.DownloadPolicy
import de.diamaneos.downloads.DownloadPolicyClient
import java.io.IOException

class DownloadServersActivity : SetupWizardActivity(
    R.layout.activity_location,
    R.drawable.baseline_download_glif,
    R.string.download_servers_title,
    R.string.download_servers_description
) {
    private lateinit var settingsItem: Item

    override fun bindViews() {
        val layout = requireViewById<GlifRecyclerLayout>(R.id.glif_layout)
        settingsItem = Item().apply {
            id = View.generateViewId()
            title = getString(R.string.download_servers_settings)
            summary = getString(R.string.download_servers_unavailable)
        }
        val group = ItemGroup().apply { addChild(settingsItem) }
        layout.adapter = RecyclerItemAdapter(group).apply {
            setOnItemSelectedListener { item ->
                if (item === settingsItem) {
                    try {
                        SetupWizard.startActivityForResult(this@DownloadServersActivity,
                            DownloadPolicyClient.settingsIntent(this@DownloadServersActivity))
                    } catch (e: ActivityNotFoundException) {
                        settingsItem.summary = getString(R.string.download_servers_unavailable)
                    } catch (e: SecurityException) {
                        settingsItem.summary = getString(R.string.download_servers_unavailable)
                    }
                }
            }
        }
    }

    override fun setupActions() {
        primaryButton.setOnClickListener { SetupWizard.next(this) }
    }

    override fun onResume() {
        super.onResume()
        settingsItem.summary = try {
            getString(when (DownloadPolicyClient.read(this).mode) {
                DownloadPolicy.PRIMARY -> R.string.download_servers_europe
                DownloadPolicy.CANADA -> R.string.download_servers_canada
                else -> R.string.download_servers_automatic
            })
        } catch (e: IOException) {
            getString(R.string.download_servers_unavailable)
        }
    }
}

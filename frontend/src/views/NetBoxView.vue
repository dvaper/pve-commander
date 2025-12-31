<template>
  <v-container fluid>
    <!-- Header mit Aktionen -->
    <v-row class="mb-2" align="center">
      <v-col>
        <div class="d-flex align-center">
          <v-icon class="mr-2" color="primary">mdi-ip-network</v-icon>
          <span class="text-h6">NetBox IPAM</span>
        </div>
      </v-col>
      <v-col cols="auto">
        <v-btn
          v-if="netboxUrl"
          color="primary"
          variant="outlined"
          size="small"
          :href="netboxUrl"
          target="_blank"
        >
          <v-icon start>mdi-open-in-new</v-icon>
          NetBox oeffnen
        </v-btn>
        <v-chip v-else color="warning" variant="tonal" size="small">
          <v-icon start size="small">mdi-alert</v-icon>
          URL nicht konfiguriert
        </v-chip>
      </v-col>
    </v-row>

    <!-- Tabs - Workflow-Reihenfolge -->
    <v-card>
      <v-tabs v-model="activeTab" color="primary">
        <v-tab value="import">
          <v-icon start>mdi-import</v-icon>
          1. VLAN-Import
        </v-tab>
        <v-tab value="networks">
          <v-icon start>mdi-lan</v-icon>
          2. Netzwerke
        </v-tab>
        <v-tab value="ips">
          <v-icon start>mdi-ip-network</v-icon>
          3. IP-Adressen
        </v-tab>
        <v-tab value="vms">
          <v-icon start>mdi-server</v-icon>
          4. VMs
        </v-tab>
      </v-tabs>

      <v-divider></v-divider>

      <v-window v-model="activeTab">
        <!-- Tab 1: VLAN-Import -->
        <v-window-item value="import">
          <v-card-text>
            <v-alert type="info" variant="tonal" class="mb-4">
              <div class="d-flex align-center">
                <v-icon start>mdi-information</v-icon>
                <div>
                  <strong>Schritt 1:</strong> Scanne den Proxmox-Cluster nach VLANs und importiere sie nach NetBox.
                  Die VLANs werden automatisch mit den zugehoerigen Prefixes angelegt.
                </div>
              </div>
            </v-alert>

            <v-btn
              color="primary"
              @click="scanProxmox"
              :loading="scanning"
              class="mb-4"
            >
              <v-icon start>mdi-magnify-scan</v-icon>
              Proxmox scannen
            </v-btn>

            <!-- Scan-Ergebnisse -->
            <template v-if="proxmoxVlans.length > 0">
              <!-- Hinweis wenn alle VLANs bereits existieren -->
              <v-alert
                v-if="newVlansCount === 0"
                type="success"
                variant="tonal"
                class="mb-4"
              >
                <div class="d-flex align-center justify-space-between">
                  <div>
                    <v-icon start>mdi-check-circle</v-icon>
                    <strong>Alle {{ proxmoxVlans.length }} VLANs sind bereits in NetBox vorhanden.</strong>
                  </div>
                  <v-btn size="small" variant="outlined" @click="activeTab = 'networks'">
                    <v-icon start>mdi-arrow-right</v-icon>
                    Zu Netzwerke
                  </v-btn>
                </div>
              </v-alert>

              <v-data-table
                v-model="selectedVlans"
                :headers="importHeaders"
                :items="proxmoxVlans"
                show-select
                density="compact"
                :items-per-page="10"
                item-value="vlan_id"
                :item-selectable="item => !item.exists_in_netbox"
              >
                <template v-slot:top>
                  <v-toolbar flat density="compact">
                    <v-toolbar-title class="text-body-1">
                      {{ proxmoxVlans.length }} VLANs in Proxmox gefunden
                      <span v-if="newVlansCount > 0" class="text-warning ml-2">
                        ({{ newVlansCount }} neu)
                      </span>
                    </v-toolbar-title>
                  </v-toolbar>
                </template>

                <template v-slot:item.vlan_id="{ item }">
                  <v-chip size="small" color="primary" variant="flat">
                    {{ item.vlan_id }}
                  </v-chip>
                </template>

                <template v-slot:item.bridge="{ item }">
                  <code>{{ item.bridge }}</code>
                </template>

                <template v-slot:item.nodes="{ item }">
                  <v-chip
                    v-for="node in item.nodes"
                    :key="node"
                    size="x-small"
                    class="mr-1"
                    variant="outlined"
                  >
                    {{ node }}
                  </v-chip>
                </template>

                <template v-slot:item.exists_in_netbox="{ item }">
                  <v-chip v-if="item.exists_in_netbox" size="small" color="success" variant="flat">
                    <v-icon start size="small">mdi-check</v-icon>
                    Vorhanden
                  </v-chip>
                  <v-chip v-else size="small" color="warning" variant="flat">
                    <v-icon start size="small">mdi-alert</v-icon>
                    Neu
                  </v-chip>
                </template>

                <template v-slot:item.prefix="{ item }">
                  <v-text-field
                    v-if="!item.exists_in_netbox"
                    v-model="item.prefix"
                    variant="outlined"
                    density="compact"
                    hide-details
                    :placeholder="`192.168.${item.vlan_id}.0/24`"
                    style="min-width: 180px"
                  ></v-text-field>
                  <span v-else class="text-grey">-</span>
                </template>
              </v-data-table>

              <!-- Import Button -->
              <v-btn
                v-if="newVlansCount > 0"
                color="success"
                @click="importVlans"
                :loading="importing"
                :disabled="selectedVlans.length === 0"
                class="mt-4"
              >
                <v-icon start>mdi-import</v-icon>
                {{ selectedVlans.length }} VLANs importieren
              </v-btn>
            </template>

            <!-- Empty State - keine VLANs in Proxmox -->
            <v-alert
              v-else-if="!scanning && scannedOnce"
              type="info"
              variant="tonal"
              class="mt-4"
            >
              <v-icon start>mdi-information</v-icon>
              Keine VLANs in Proxmox gefunden. Pruefe die Bridge-Konfiguration auf den Nodes.
            </v-alert>

            <!-- Import-Ergebnis -->
            <v-alert
              v-if="importResult"
              :type="importResult.errors?.length > 0 ? 'warning' : 'success'"
              variant="tonal"
              class="mt-4"
              closable
              @click:close="importResult = null"
            >
              <div v-if="importResult.imported?.length > 0">
                <strong>Importiert:</strong> VLANs {{ importResult.imported.join(', ') }}
              </div>
              <div v-if="importResult.skipped?.length > 0">
                <strong>Uebersprungen:</strong> VLANs {{ importResult.skipped.join(', ') }} (bereits vorhanden)
              </div>
              <div v-if="importResult.errors?.length > 0">
                <strong>Fehler:</strong>
                <ul>
                  <li v-for="(error, i) in importResult.errors" :key="i">{{ error }}</li>
                </ul>
              </div>
              <div class="mt-2">
                <v-btn size="small" variant="outlined" @click="activeTab = 'networks'">
                  <v-icon start>mdi-arrow-right</v-icon>
                  Weiter zu Netzwerke
                </v-btn>
              </div>
            </v-alert>
          </v-card-text>
        </v-window-item>

        <!-- Tab 2: Netzwerke (VLANs + Prefixes) -->
        <v-window-item value="networks">
          <v-card-text>
            <!-- Empty State wenn weder VLANs noch Prefixes vorhanden -->
            <v-alert
              v-if="vlans.length === 0 && prefixes.length === 0 && !loadingVlans && !loadingPrefixes"
              type="warning"
              variant="tonal"
              class="mb-4"
            >
              <div class="d-flex align-center justify-space-between">
                <div>
                  <v-icon start>mdi-alert</v-icon>
                  <strong>Noch keine Netzwerke vorhanden.</strong>
                  Importiere zuerst VLANs aus Proxmox.
                </div>
                <v-btn size="small" variant="outlined" @click="activeTab = 'import'">
                  <v-icon start>mdi-import</v-icon>
                  Zum VLAN-Import
                </v-btn>
              </div>
            </v-alert>

            <!-- Zwei-Spalten-Layout: VLANs links, Prefixes rechts -->
            <v-row v-if="vlans.length > 0 || prefixes.length > 0 || loadingVlans || loadingPrefixes">
              <!-- VLANs (aus Proxmox importiert) -->
              <v-col cols="12" lg="6">
                <v-card variant="outlined" class="h-100">
                  <v-toolbar flat density="compact" color="transparent">
                    <v-icon start color="primary">mdi-server-network</v-icon>
                    <v-toolbar-title class="text-body-1 font-weight-medium">
                      VLANs
                      <span class="text-caption text-grey ml-1">(Proxmox)</span>
                    </v-toolbar-title>
                    <v-spacer></v-spacer>
                    <v-chip size="x-small" variant="tonal" class="mr-2">{{ vlans.length }}</v-chip>
                    <v-btn icon variant="text" size="small" @click="loadVlans" :loading="loadingVlans">
                      <v-icon size="small">mdi-refresh</v-icon>
                    </v-btn>
                  </v-toolbar>
                  <v-divider></v-divider>
                  <v-data-table
                    :headers="vlanHeadersCompact"
                    :items="vlans"
                    :loading="loadingVlans"
                    density="compact"
                    :items-per-page="10"
                    :items-per-page-options="[10, 25, 50]"
                  >
                    <template v-slot:item.id="{ item }">
                      <v-chip size="x-small" color="primary" variant="flat">
                        {{ item.id }}
                      </v-chip>
                    </template>
                    <template v-slot:item.bridge="{ item }">
                      <code class="text-caption">{{ item.bridge }}</code>
                    </template>
                  </v-data-table>
                </v-card>
              </v-col>

              <!-- Prefixes (NetBox IPAM) -->
              <v-col cols="12" lg="6">
                <v-card variant="outlined" class="h-100">
                  <v-toolbar flat density="compact" color="transparent">
                    <v-icon start color="secondary">mdi-ip-network</v-icon>
                    <v-toolbar-title class="text-body-1 font-weight-medium">
                      Prefixes
                      <span class="text-caption text-grey ml-1">(NetBox)</span>
                    </v-toolbar-title>
                    <v-spacer></v-spacer>
                    <v-chip size="x-small" variant="tonal" class="mr-2">{{ prefixes.length }}</v-chip>
                    <v-btn icon variant="text" size="small" @click="loadPrefixes" :loading="loadingPrefixes">
                      <v-icon size="small">mdi-refresh</v-icon>
                    </v-btn>
                  </v-toolbar>
                  <v-divider></v-divider>
                  <v-data-table
                    :headers="prefixHeadersCompact"
                    :items="prefixes"
                    :loading="loadingPrefixes"
                    density="compact"
                    :items-per-page="10"
                    :items-per-page-options="[10, 25, 50]"
                  >
                    <template v-slot:item.prefix="{ item }">
                      <code class="text-caption">{{ item.prefix }}</code>
                    </template>
                    <template v-slot:item.vlan="{ item }">
                      <v-chip v-if="item.vlan" size="x-small" color="primary" variant="outlined">
                        {{ item.vlan }}
                      </v-chip>
                      <span v-else class="text-grey">-</span>
                    </template>
                    <template v-slot:item.utilization="{ item }">
                      <div class="d-flex align-center" style="min-width: 80px">
                        <v-progress-linear
                          :model-value="item.utilization || 0"
                          height="6"
                          rounded
                          :color="item.utilization > 80 ? 'error' : item.utilization > 50 ? 'warning' : 'success'"
                          class="mr-1"
                          style="max-width: 50px"
                        >
                        </v-progress-linear>
                        <span class="text-caption">{{ item.utilization || 0 }}%</span>
                      </div>
                    </template>
                  </v-data-table>
                </v-card>
              </v-col>
            </v-row>

            <!-- Hinweis zur IP-Synchronisation -->
            <v-alert
              v-if="prefixes.length > 0"
              type="info"
              variant="tonal"
              class="mt-4"
              density="compact"
            >
              <div class="d-flex align-center justify-space-between">
                <div>
                  <v-icon start size="small">mdi-lightbulb</v-icon>
                  Um die Auslastung zu aktualisieren, synchronisiere die IP-Adressen aus Proxmox.
                </div>
                <v-btn size="small" variant="outlined" @click="activeTab = 'ips'">
                  <v-icon start>mdi-sync</v-icon>
                  IPs synchronisieren
                </v-btn>
              </div>
            </v-alert>
          </v-card-text>
        </v-window-item>

        <!-- Tab 3: IP-Adressen -->
        <v-window-item value="ips">
          <v-card-text>
            <v-alert type="info" variant="tonal" class="mb-4">
              <div class="d-flex align-center">
                <v-icon start>mdi-information</v-icon>
                <div>
                  <strong>Schritt 3:</strong> Synchronisiere IP-Adressen aus laufenden Proxmox VMs nach NetBox.
                  Dies aktualisiert die Auslastung der Prefixes.
                </div>
              </div>
            </v-alert>

            <!-- Sync Button -->
            <div class="d-flex align-center mb-4">
              <v-btn
                color="primary"
                @click="syncIPs"
                :loading="syncing"
              >
                <v-icon start>mdi-sync</v-icon>
                IPs synchronisieren
              </v-btn>
              <span v-if="lastSyncTime" class="ml-4 text-caption text-grey">
                Letzter Sync: {{ lastSyncTime }}
              </span>
            </div>

            <!-- Sync-Ergebnis -->
            <v-alert
              v-if="syncResult"
              :type="syncResult.errors?.length > 0 ? 'warning' : 'success'"
              variant="tonal"
              class="mb-4"
              closable
              @click:close="syncResult = null"
            >
              <div class="d-flex align-center">
                <div>
                  <strong>{{ syncResult.scanned }}</strong> VMs gescannt |
                  <strong>{{ syncResult.created }}</strong> IPs angelegt |
                  <strong>{{ syncResult.skipped }}</strong> bereits vorhanden |
                  <strong>{{ syncResult.released || 0 }}</strong> freigegeben
                </div>
              </div>
              <div v-if="syncResult.errors?.length > 0" class="mt-2">
                <strong>Fehler:</strong>
                <ul class="mb-0">
                  <li v-for="(error, i) in syncResult.errors" :key="i">{{ error }}</li>
                </ul>
              </div>
            </v-alert>

            <!-- Scanned IPs expandable -->
            <v-expansion-panels v-if="syncResult?.ips?.length > 0" class="mb-4">
              <v-expansion-panel>
                <v-expansion-panel-title>
                  <v-icon start>mdi-server</v-icon>
                  {{ syncResult.ips.length }} VMs mit IP gefunden
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <v-data-table
                    :headers="syncIpHeaders"
                    :items="syncResult.ips"
                    density="compact"
                    :items-per-page="10"
                  >
                    <template v-slot:item.ip="{ item }">
                      <code>{{ item.ip }}</code>
                    </template>
                    <template v-slot:item.source="{ item }">
                      <v-chip size="x-small" :color="item.source === 'guest-agent' ? 'success' : 'info'" variant="outlined">
                        {{ item.source }}
                      </v-chip>
                    </template>
                    <template v-slot:item.exists_in_netbox="{ item }">
                      <v-icon v-if="item.exists_in_netbox" color="success" size="small">mdi-check-circle</v-icon>
                      <v-chip v-else size="x-small" color="warning" variant="flat">NEU</v-chip>
                    </template>
                    <template v-slot:item.status="{ item }">
                      <v-chip size="x-small" :color="item.status === 'running' ? 'success' : 'grey'" variant="outlined">
                        {{ item.status }}
                      </v-chip>
                    </template>
                  </v-data-table>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>

            <!-- Freigegebene IPs -->
            <v-expansion-panels v-if="syncResult?.released_ips?.length > 0" class="mb-4">
              <v-expansion-panel>
                <v-expansion-panel-title>
                  <v-icon start color="warning">mdi-delete-circle</v-icon>
                  {{ syncResult.released_ips.length }} verwaiste IPs freigegeben
                </v-expansion-panel-title>
                <v-expansion-panel-text>
                  <v-data-table
                    :headers="releasedIpHeaders"
                    :items="syncResult.released_ips"
                    density="compact"
                    :items-per-page="10"
                  >
                    <template v-slot:item.ip="{ item }">
                      <code>{{ item.ip }}</code>
                    </template>
                  </v-data-table>
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>

            <!-- Prefix-Auslastung -->
            <v-data-table
              :headers="prefixUtilizationHeaders"
              :items="prefixes"
              :loading="loadingPrefixes"
              density="compact"
              :items-per-page="10"
            >
              <template v-slot:top>
                <v-toolbar flat density="compact">
                  <v-toolbar-title class="text-body-1">Prefix-Auslastung</v-toolbar-title>
                  <v-spacer></v-spacer>
                  <v-btn icon variant="text" size="small" @click="loadPrefixes" :loading="loadingPrefixes">
                    <v-icon size="small">mdi-refresh</v-icon>
                  </v-btn>
                </v-toolbar>
              </template>

              <template v-slot:item.prefix="{ item }">
                <code>{{ item.prefix }}</code>
              </template>

              <template v-slot:item.vlan="{ item }">
                <v-chip v-if="item.vlan" size="small" color="primary" variant="outlined">
                  VLAN {{ item.vlan }}
                </v-chip>
                <span v-else class="text-grey">-</span>
              </template>

              <template v-slot:item.utilization="{ item }">
                <div class="d-flex align-center" style="min-width: 150px">
                  <v-progress-linear
                    :model-value="item.utilization || 0"
                    height="12"
                    rounded
                    :color="item.utilization > 80 ? 'error' : item.utilization > 50 ? 'warning' : 'success'"
                    class="mr-2"
                  >
                  </v-progress-linear>
                  <span class="text-body-2 font-weight-medium" style="min-width: 40px">
                    {{ item.utilization || 0 }}%
                  </span>
                </div>
              </template>
            </v-data-table>
          </v-card-text>
        </v-window-item>

        <!-- Tab 4: VMs -->
        <v-window-item value="vms">
          <v-card-text>
            <v-alert type="info" variant="tonal" class="mb-4">
              <div class="d-flex align-center">
                <v-icon start>mdi-information</v-icon>
                <div>
                  <strong>Schritt 4:</strong> Synchronisiere VMs aus Proxmox nach NetBox.
                  Verwaiste Eintraege (VM nicht mehr in Proxmox) koennen geloescht werden.
                </div>
              </div>
            </v-alert>

            <!-- Scan Button -->
            <div class="d-flex align-center mb-4">
              <v-btn
                color="primary"
                @click="scanProxmoxVMs"
                :loading="scanningVMs"
              >
                <v-icon start>mdi-magnify-scan</v-icon>
                Proxmox scannen
              </v-btn>
              <v-btn
                v-if="selectedVMsToSync.length > 0"
                color="success"
                class="ml-2"
                @click="syncSelectedVMs"
                :loading="syncingVMs"
              >
                <v-icon start>mdi-sync</v-icon>
                {{ selectedVMsToSync.length }} VMs synchronisieren
              </v-btn>
              <v-btn
                v-if="registeredVMsCount > 0"
                color="info"
                class="ml-2"
                @click="updateAllRegisteredVMs"
                :loading="updatingVMs"
              >
                <v-icon start>mdi-refresh</v-icon>
                Alle aktualisieren
              </v-btn>
            </div>

            <!-- Filter-Buttons und Statistik -->
            <div v-if="proxmoxVMs.length > 0" class="d-flex flex-wrap align-center gap-2 mb-4">
              <!-- Filter-Buttons -->
              <v-chip-group
                v-model="vmStatusFilter"
                mandatory
                selected-class="text-white"
                class="mr-4"
              >
                <v-chip
                  value="all"
                  size="small"
                  variant="elevated"
                  :color="vmStatusFilter === 'all' ? 'primary' : undefined"
                >
                  Alle ({{ proxmoxVMs.length }})
                </v-chip>
                <v-tooltip text="Registriert in NetBox" location="top">
                  <template v-slot:activator="{ props }">
                    <v-chip
                      v-bind="props"
                      value="registered"
                      size="small"
                      variant="elevated"
                      color="success"
                      :class="{ 'opacity-60': vmStatusFilter !== 'registered' }"
                    >
                      <v-icon start size="small">mdi-check-circle</v-icon>
                      {{ registeredVMsCount }}
                    </v-chip>
                  </template>
                </v-tooltip>
                <v-tooltip text="Nicht in NetBox registriert" location="top">
                  <template v-slot:activator="{ props }">
                    <v-chip
                      v-bind="props"
                      value="unregistered"
                      size="small"
                      variant="elevated"
                      color="warning"
                      :class="{ 'opacity-60': vmStatusFilter !== 'unregistered' }"
                    >
                      <v-icon start size="small">mdi-alert</v-icon>
                      {{ unregisteredVMsCount }}
                    </v-chip>
                  </template>
                </v-tooltip>
                <v-tooltip v-if="orphanedVMsCount > 0" text="In NetBox, aber nicht in Proxmox" location="top">
                  <template v-slot:activator="{ props }">
                    <v-chip
                      v-bind="props"
                      value="orphaned"
                      size="small"
                      variant="elevated"
                      color="error"
                      :class="{ 'opacity-60': vmStatusFilter !== 'orphaned' }"
                    >
                      <v-icon start size="small">mdi-delete-alert</v-icon>
                      {{ orphanedVMsCount }}
                    </v-chip>
                  </template>
                </v-tooltip>
              </v-chip-group>
            </div>

            <!-- VM-Sync Ergebnis -->
            <v-alert
              v-if="vmSyncResult"
              :type="vmSyncResult.errors?.length > 0 ? 'warning' : 'success'"
              variant="tonal"
              class="mb-4"
              closable
              @click:close="vmSyncResult = null"
            >
              <div>
                <strong>{{ vmSyncResult.synced }}</strong> VMs synchronisiert
                <span v-if="vmSyncResult.errors?.length > 0">
                  | <strong>{{ vmSyncResult.errors.length }}</strong> Fehler
                </span>
              </div>
              <div v-if="vmSyncResult.errors?.length > 0" class="mt-2">
                <ul class="mb-0">
                  <li v-for="(error, i) in vmSyncResult.errors" :key="i">{{ error }}</li>
                </ul>
              </div>
            </v-alert>

            <!-- VM-Update Ergebnis -->
            <v-alert
              v-if="vmUpdateResult"
              :type="vmUpdateResult.errors?.length > 0 ? 'warning' : 'success'"
              variant="tonal"
              class="mb-4"
              closable
              @click:close="vmUpdateResult = null"
            >
              <div>
                <strong>{{ vmUpdateResult.updated }}</strong> VMs aktualisiert
                <span v-if="vmUpdateResult.errors?.length > 0">
                  | <strong>{{ vmUpdateResult.errors.length }}</strong> Fehler
                </span>
              </div>
              <div v-if="vmUpdateResult.errors?.length > 0" class="mt-2">
                <ul class="mb-0">
                  <li v-for="(error, i) in vmUpdateResult.errors" :key="i">{{ error }}</li>
                </ul>
              </div>
            </v-alert>

            <!-- Bulk Delete Ergebnis -->
            <v-alert
              v-if="bulkDeleteResult"
              :type="bulkDeleteResult.failed > 0 ? 'warning' : 'success'"
              variant="tonal"
              class="mb-4"
              closable
              @click:close="bulkDeleteResult = null"
            >
              <div>
                <strong>{{ bulkDeleteResult.deleted }}</strong> VM(s) geloescht
                <span v-if="bulkDeleteResult.failed > 0">
                  | <strong>{{ bulkDeleteResult.failed }}</strong> fehlgeschlagen
                </span>
              </div>
              <div v-if="bulkDeleteResult.errors?.length > 0" class="mt-2">
                <ul class="mb-0">
                  <li v-for="(error, i) in bulkDeleteResult.errors" :key="i">{{ error }}</li>
                </ul>
              </div>
            </v-alert>

            <!-- Bulk Action Toolbar -->
            <v-toolbar
              v-if="selectedVMsToSync.length > 0"
              density="compact"
              color="primary"
              class="mb-4 rounded"
            >
              <v-toolbar-title class="text-body-2">
                {{ selectedVMsToSync.length }} VM{{ selectedVMsToSync.length > 1 ? 's' : '' }} ausgewaehlt
              </v-toolbar-title>

              <v-spacer></v-spacer>

              <!-- Sync Button (fuer unregistered) -->
              <v-btn
                v-if="vmStatusFilter === 'unregistered' || vmStatusFilter === 'all'"
                variant="elevated"
                color="success"
                size="small"
                :loading="bulkSyncing"
                :disabled="bulkSyncing || bulkUpdating || bulkDeleting"
                @click="bulkSyncVMs"
                class="mr-2"
              >
                <v-icon start>mdi-sync</v-icon>
                Alle synchronisieren
              </v-btn>

              <!-- Update Button (fuer registered) -->
              <v-btn
                v-if="vmStatusFilter === 'registered'"
                variant="elevated"
                color="info"
                size="small"
                :loading="bulkUpdating"
                :disabled="bulkSyncing || bulkUpdating || bulkDeleting"
                @click="bulkUpdateVMs"
                class="mr-2"
              >
                <v-icon start>mdi-refresh</v-icon>
                Alle aktualisieren
              </v-btn>

              <!-- Delete Button (fuer orphaned) -->
              <v-btn
                v-if="vmStatusFilter === 'orphaned'"
                variant="elevated"
                color="error"
                size="small"
                :loading="bulkDeleting"
                :disabled="bulkSyncing || bulkUpdating || bulkDeleting"
                @click="confirmBulkDelete"
                class="mr-2"
              >
                <v-icon start>mdi-delete</v-icon>
                Alle loeschen
              </v-btn>

              <!-- Clear Selection -->
              <v-btn
                variant="text"
                size="small"
                @click="selectedVMsToSync = []"
              >
                <v-icon>mdi-close</v-icon>
              </v-btn>
            </v-toolbar>

            <!-- Suche -->
            <v-text-field
              v-if="proxmoxVMs.length > 0"
              v-model="vmSearchQuery"
              prepend-inner-icon="mdi-magnify"
              label="VM suchen (Name, IP, VMID, Node)"
              density="compact"
              variant="outlined"
              clearable
              hide-details
              class="mb-4"
              style="max-width: 400px;"
            />

            <!-- VM-Tabelle -->
            <v-data-table
              v-model="selectedVMsToSync"
              :headers="vmHeaders"
              :items="filteredProxmoxVMs"
              :loading="scanningVMs"
              show-select
              density="compact"
              :items-per-page="10"
              :item-value="getItemValue"
              :item-selectable="getItemSelectable"
            >
              <template v-slot:item.vmid="{ item }">
                <v-chip v-if="item.vmid" size="small" color="primary" variant="flat">
                  {{ item.vmid }}
                </v-chip>
                <span v-else class="text-grey">-</span>
              </template>

              <template v-slot:item.node="{ item }">
                <v-chip v-if="item.node" size="x-small" variant="outlined">
                  {{ item.node }}
                </v-chip>
                <span v-else class="text-grey">-</span>
              </template>

              <template v-slot:item.ip_address="{ item }">
                <code v-if="item.ip_address">{{ item.ip_address }}</code>
                <span v-else class="text-grey">-</span>
              </template>

              <template v-slot:item.cores="{ item }">
                <span v-if="item.cores">{{ item.cores }} vCPU</span>
                <span v-else class="text-grey">-</span>
              </template>

              <template v-slot:item.memory_gb="{ item }">
                <span v-if="item.memory_gb">{{ item.memory_gb }} GB</span>
                <span v-else class="text-grey">-</span>
              </template>

              <template v-slot:item.status="{ item }">
                <v-chip
                  size="small"
                  :color="item.status === 'registered' ? 'success' : item.status === 'orphaned' ? 'error' : 'warning'"
                  variant="flat"
                >
                  <v-icon start size="small">
                    {{ item.status === 'registered' ? 'mdi-check-circle' : item.status === 'orphaned' ? 'mdi-delete-alert' : 'mdi-alert' }}
                  </v-icon>
                  {{ item.status === 'registered' ? 'Registriert' : item.status === 'orphaned' ? 'Verwaist' : 'Nicht registriert' }}
                </v-chip>
              </template>

              <template v-slot:item.actions="{ item }">
                <v-btn
                  v-if="item.status === 'unregistered'"
                  size="small"
                  color="success"
                  variant="text"
                  @click="syncSingleVM(item)"
                  :loading="syncingVMId === item.vmid"
                  title="In NetBox registrieren"
                >
                  <v-icon>mdi-sync</v-icon>
                </v-btn>
                <v-btn
                  v-if="item.status === 'registered'"
                  size="small"
                  color="info"
                  variant="text"
                  @click="updateSingleVM(item)"
                  :loading="updatingVMId === item.vmid"
                  title="Specs aktualisieren"
                >
                  <v-icon>mdi-refresh</v-icon>
                </v-btn>
                <v-btn
                  v-if="item.status === 'orphaned'"
                  size="small"
                  color="error"
                  variant="text"
                  @click="confirmDeleteOrphanedVM(item)"
                  :loading="deletingVMId === item.netbox_vm_id"
                  title="Aus NetBox loeschen"
                >
                  <v-icon>mdi-delete</v-icon>
                </v-btn>
              </template>
            </v-data-table>
          </v-card-text>
        </v-window-item>
      </v-window>
    </v-card>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="deleteDialog" max-width="500">
      <v-card>
        <v-card-title class="text-h6">
          <v-icon start color="error">mdi-delete-alert</v-icon>
          Verwaiste VM loeschen
        </v-card-title>
        <v-card-text>
          <p>Moechtest du die verwaiste VM <strong>{{ vmToDelete?.name }}</strong> aus NetBox loeschen?</p>
          <p class="text-caption text-grey">
            Die IP-Adresse {{ vmToDelete?.ip_address || '(keine)' }} wird ebenfalls freigegeben.
          </p>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn variant="text" @click="deleteDialog = false">Abbrechen</v-btn>
          <v-btn color="error" variant="flat" @click="deleteOrphanedVM" :loading="deletingVM">
            <v-icon start>mdi-delete</v-icon>
            Loeschen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import api from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useConfirmDialog } from '@/composables/useConfirmDialog'

const authStore = useAuthStore()
const { confirm } = useConfirmDialog()

// NetBox URL: wird aus Settings geladen
const netboxUrl = ref(null)

// Aktiver Tab - Default ist Import fuer neue User
const activeTab = ref('import')

// Scan-Status
const scannedOnce = ref(false)

// VLANs
const vlans = ref([])
const loadingVlans = ref(false)
const vlanHeaders = [
  { title: 'VLAN ID', key: 'id', width: '100px' },
  { title: 'Name', key: 'name' },
  { title: 'Prefix', key: 'prefix' },
  { title: 'Bridge', key: 'bridge', width: '120px' },
]
// Kompakte Header fuer Zwei-Spalten-Layout
const vlanHeadersCompact = [
  { title: 'ID', key: 'id', width: '60px' },
  { title: 'Name', key: 'name' },
  { title: 'Bridge', key: 'bridge', width: '100px' },
]

// Prefixes
const prefixes = ref([])
const loadingPrefixes = ref(false)
const prefixHeaders = [
  { title: 'Prefix', key: 'prefix' },
  { title: 'VLAN', key: 'vlan', width: '120px' },
  { title: 'Beschreibung', key: 'description' },
  { title: 'Auslastung', key: 'utilization', width: '180px' },
]
// Kompakte Header fuer Zwei-Spalten-Layout
const prefixHeadersCompact = [
  { title: 'Prefix', key: 'prefix' },
  { title: 'VLAN', key: 'vlan', width: '70px' },
  { title: 'Auslastung', key: 'utilization', width: '100px' },
]
const prefixUtilizationHeaders = [
  { title: 'Prefix', key: 'prefix' },
  { title: 'VLAN', key: 'vlan', width: '120px' },
  { title: 'Beschreibung', key: 'description' },
  { title: 'Auslastung', key: 'utilization', width: '200px' },
]

// IP Sync
const syncing = ref(false)
const syncResult = ref(null)
const lastSyncTime = ref(null)
const syncIpHeaders = [
  { title: 'VMID', key: 'vmid', width: '80px' },
  { title: 'Name', key: 'name' },
  { title: 'IP', key: 'ip', width: '140px' },
  { title: 'Quelle', key: 'source', width: '100px' },
  { title: 'Status', key: 'status', width: '100px' },
  { title: 'In NetBox', key: 'exists_in_netbox', width: '100px' },
]

const releasedIpHeaders = [
  { title: 'IP', key: 'ip', width: '140px' },
  { title: 'Beschreibung', key: 'description' },
  { title: 'Grund', key: 'reason' },
]

// VM Sync (Tab 4)
const proxmoxVMs = ref([])
const selectedVMsToSync = ref([])
const selectedVMsToUpdate = ref([])
const vmStatusFilter = ref('all')
const vmSearchQuery = ref('')
const scanningVMs = ref(false)
const syncingVMs = ref(false)
const syncingVMId = ref(null)
const updatingVMs = ref(false)
const updatingVMId = ref(null)
const deletingVMId = ref(null)
const deletingVM = ref(false)
const vmSyncResult = ref(null)
const vmUpdateResult = ref(null)
const deleteDialog = ref(false)
const vmToDelete = ref(null)

// Bulk Action State
const bulkSyncing = ref(false)
const bulkUpdating = ref(false)
const bulkDeleting = ref(false)
const bulkDeleteResult = ref(null)

const vmHeaders = [
  { title: 'VMID', key: 'vmid', width: '80px' },
  { title: 'Name', key: 'name' },
  { title: 'Node', key: 'node', width: '100px' },
  { title: 'IP', key: 'ip_address', width: '140px' },
  { title: 'CPU', key: 'cores', width: '80px' },
  { title: 'RAM', key: 'memory_gb', width: '80px' },
  { title: 'Status', key: 'status', width: '150px' },
  { title: 'Aktion', key: 'actions', width: '80px', sortable: false },
]

// Computed: VM-Statistiken
const registeredVMsCount = computed(() => {
  return proxmoxVMs.value.filter(vm => vm.status === 'registered').length
})

const unregisteredVMsCount = computed(() => {
  return proxmoxVMs.value.filter(vm => vm.status === 'unregistered').length
})

const orphanedVMsCount = computed(() => {
  return proxmoxVMs.value.filter(vm => vm.status === 'orphaned').length
})

// Gefilterte VMs basierend auf Status-Filter und Suche
const filteredProxmoxVMs = computed(() => {
  let result = proxmoxVMs.value

  // Status-Filter
  if (vmStatusFilter.value !== 'all') {
    result = result.filter(vm => vm.status === vmStatusFilter.value)
  }

  // Text-Suche
  if (vmSearchQuery.value?.trim()) {
    const query = vmSearchQuery.value.toLowerCase().trim()
    result = result.filter(vm =>
      vm.name?.toLowerCase().includes(query) ||
      vm.ip?.toLowerCase().includes(query) ||
      String(vm.vmid).includes(query) ||
      vm.node?.toLowerCase().includes(query)
    )
  }

  return result
})

// Selection bei Filter-Wechsel zuruecksetzen
watch(vmStatusFilter, () => {
  selectedVMsToSync.value = []
})

// Bestimmt welche Items selektierbar sind (basierend auf Filter)
function getItemSelectable(item) {
  // Bei "all" nur unregistered selektierbar (Standard-Verhalten)
  if (vmStatusFilter.value === 'all') {
    return item.status === 'unregistered'
  }
  // Bei spezifischem Filter nur passende Status selektierbar
  return item.status === vmStatusFilter.value
}

// Bestimmt den Wert fuer Selection (vmid oder netbox_vm_id fuer orphaned)
function getItemValue(item) {
  // Orphaned VMs haben vmid: null, daher netbox_vm_id nutzen
  return item.vmid || item.netbox_vm_id
}

// Import
const proxmoxVlans = ref([])
const selectedVlans = ref([])
const scanning = ref(false)
const importing = ref(false)
const importResult = ref(null)

// Anzahl neuer VLANs (nicht in NetBox)
const newVlansCount = computed(() => {
  return proxmoxVlans.value.filter(v => !v.exists_in_netbox).length
})

const importHeaders = [
  { title: 'VLAN ID', key: 'vlan_id', width: '100px' },
  { title: 'Bridge', key: 'bridge', width: '120px' },
  { title: 'Nodes', key: 'nodes' },
  { title: 'Status', key: 'exists_in_netbox', width: '120px' },
  { title: 'Prefix (editierbar)', key: 'prefix', width: '200px' },
]

// VLANs laden
async function loadVlans() {
  loadingVlans.value = true
  try {
    const response = await api.get('/api/netbox/vlans')
    vlans.value = response.data
  } catch (error) {
    console.error('Fehler beim Laden der VLANs:', error)
  } finally {
    loadingVlans.value = false
  }
}

// Prefixes laden
async function loadPrefixes() {
  loadingPrefixes.value = true
  try {
    const response = await api.get('/api/netbox/prefixes')
    prefixes.value = response.data
  } catch (error) {
    console.error('Fehler beim Laden der Prefixes:', error)
  } finally {
    loadingPrefixes.value = false
  }
}

// IPs mit Proxmox synchronisieren
async function syncIPs() {
  syncing.value = true
  syncResult.value = null
  try {
    const response = await api.post('/api/netbox/sync-ips')
    syncResult.value = response.data
    lastSyncTime.value = new Date().toLocaleTimeString('de-DE')

    // Prefixes neu laden um Auslastung zu aktualisieren
    await loadPrefixes()
  } catch (error) {
    console.error('Fehler beim IP-Sync:', error)
    syncResult.value = {
      scanned: 0,
      created: 0,
      skipped: 0,
      errors: [error.response?.data?.detail || 'Unbekannter Fehler'],
      ips: []
    }
  } finally {
    syncing.value = false
  }
}

// Proxmox scannen
async function scanProxmox() {
  scanning.value = true
  importResult.value = null
  scannedOnce.value = true
  try {
    const response = await api.get('/api/netbox/proxmox-vlans')
    proxmoxVlans.value = response.data.vlans.map(v => ({
      ...v,
      prefix: v.exists_in_netbox ? '' : `192.168.${v.vlan_id}.0/24`
    }))
    lastVlanScan.value = response.data.cached_at
    vlanChanges.value = {
      hasChanges: response.data.has_changes,
      newVlans: response.data.new_vlans || []
    }
    // Nur VLANs auswaehlen, die noch nicht in NetBox sind
    selectedVlans.value = proxmoxVlans.value
      .filter(v => !v.exists_in_netbox)
      .map(v => v.vlan_id)
  } catch (error) {
    console.error('Fehler beim Scannen:', error)
  } finally {
    scanning.value = false
  }
}

// VLANs importieren
async function importVlans() {
  importing.value = true
  try {
    const vlansToImport = proxmoxVlans.value
      .filter(v => selectedVlans.value.includes(v.vlan_id))
      .map(v => ({
        vlan_id: v.vlan_id,
        prefix: v.prefix || null
      }))

    const response = await api.post('/api/netbox/import-vlans', {
      vlans: vlansToImport
    })
    importResult.value = response.data

    // VLANs und Prefixes neu laden
    await loadVlans()
    await loadPrefixes()

    // Scan-Ergebnisse aktualisieren
    await scanProxmox()
  } catch (error) {
    console.error('Fehler beim Import:', error)
    importResult.value = {
      imported: [],
      skipped: [],
      errors: [error.response?.data?.detail || 'Unbekannter Fehler']
    }
  } finally {
    importing.value = false
  }
}

// NetBox URL laden
async function loadNetboxUrl() {
  try {
    const response = await api.get('/api/settings/netbox-url')
    netboxUrl.value = response.data.url
  } catch (error) {
    console.error('Fehler beim Laden der NetBox URL:', error)
  }
}

// ============================================
// VM Sync Funktionen (Tab 4)
// ============================================

// Proxmox VMs scannen
async function scanProxmoxVMs() {
  scanningVMs.value = true
  vmSyncResult.value = null
  try {
    const response = await api.get('/api/netbox/proxmox-vms')
    proxmoxVMs.value = response.data.vms
    lastVMScan.value = response.data.cached_at
    vmChanges.value = {
      hasChanges: response.data.has_changes,
      newVms: response.data.new_vms || [],
      removedVms: response.data.removed_vms || []
    }
    // Nur nicht-registrierte VMs vorauswählen
    selectedVMsToSync.value = proxmoxVMs.value
      .filter(vm => vm.status === 'unregistered' && vm.vmid)
      .map(vm => vm.vmid)
  } catch (error) {
    console.error('Fehler beim Scannen der VMs:', error)
  } finally {
    scanningVMs.value = false
  }
}

// Ausgewählte VMs synchronisieren
async function syncSelectedVMs() {
  if (selectedVMsToSync.value.length === 0) return

  syncingVMs.value = true
  vmSyncResult.value = null
  try {
    const response = await api.post('/api/netbox/sync-vms', {
      vmids: selectedVMsToSync.value
    })
    vmSyncResult.value = response.data
    // VMs neu scannen um Status zu aktualisieren
    await scanProxmoxVMs()
  } catch (error) {
    console.error('Fehler beim Synchronisieren:', error)
    vmSyncResult.value = {
      synced: 0,
      skipped: 0,
      errors: [error.response?.data?.detail || 'Unbekannter Fehler'],
      details: []
    }
  } finally {
    syncingVMs.value = false
  }
}

// Einzelne VM synchronisieren
async function syncSingleVM(vm) {
  if (!vm.vmid) return

  syncingVMId.value = vm.vmid
  try {
    const response = await api.post('/api/netbox/sync-vms', {
      vmids: [vm.vmid]
    })
    vmSyncResult.value = response.data
    // VMs neu scannen um Status zu aktualisieren
    await scanProxmoxVMs()
  } catch (error) {
    console.error('Fehler beim Synchronisieren:', error)
    vmSyncResult.value = {
      synced: 0,
      skipped: 0,
      errors: [error.response?.data?.detail || 'Unbekannter Fehler'],
      details: []
    }
  } finally {
    syncingVMId.value = null
  }
}

// Alle registrierten VMs aktualisieren
async function updateAllRegisteredVMs() {
  const registeredVmids = proxmoxVMs.value
    .filter(vm => vm.status === 'registered' && vm.vmid)
    .map(vm => vm.vmid)

  if (registeredVmids.length === 0) return

  updatingVMs.value = true
  vmUpdateResult.value = null
  try {
    const response = await api.post('/api/netbox/update-vms', {
      vmids: registeredVmids
    })
    vmUpdateResult.value = response.data
  } catch (error) {
    console.error('Fehler beim Aktualisieren:', error)
    vmUpdateResult.value = {
      updated: 0,
      errors: [error.response?.data?.detail || 'Unbekannter Fehler'],
      details: []
    }
  } finally {
    updatingVMs.value = false
  }
}

// Einzelne registrierte VM aktualisieren
async function updateSingleVM(vm) {
  if (!vm.vmid) return

  updatingVMId.value = vm.vmid
  try {
    const response = await api.post('/api/netbox/update-vms', {
      vmids: [vm.vmid]
    })
    vmUpdateResult.value = response.data
  } catch (error) {
    console.error('Fehler beim Aktualisieren:', error)
    vmUpdateResult.value = {
      updated: 0,
      errors: [error.response?.data?.detail || 'Unbekannter Fehler'],
      details: []
    }
  } finally {
    updatingVMId.value = null
  }
}

// Lösch-Dialog öffnen
function confirmDeleteOrphanedVM(vm) {
  vmToDelete.value = vm
  deleteDialog.value = true
}

// Verwaiste VM löschen
async function deleteOrphanedVM() {
  if (!vmToDelete.value?.netbox_vm_id) return

  deletingVM.value = true
  deletingVMId.value = vmToDelete.value.netbox_vm_id
  try {
    await api.delete(`/api/netbox/vms/${vmToDelete.value.netbox_vm_id}`)
    deleteDialog.value = false
    vmToDelete.value = null
    // VMs neu scannen
    await scanProxmoxVMs()
  } catch (error) {
    console.error('Fehler beim Löschen:', error)
  } finally {
    deletingVM.value = false
    deletingVMId.value = null
  }
}

// ============================================
// Bulk Action Funktionen
// ============================================

// Bulk sync ausgewaehlter unregistrierter VMs
async function bulkSyncVMs() {
  if (selectedVMsToSync.value.length === 0) return

  // ConfirmDialog wenn ui_beta aktiviert
  if (authStore.currentUiBeta) {
    const confirmed = await confirm({
      title: 'VMs synchronisieren?',
      message: `${selectedVMsToSync.value.length} VM(s) werden nach NetBox synchronisiert.`,
      icon: 'mdi-sync',
      iconColor: 'success',
      confirmLabel: 'Synchronisieren',
      confirmColor: 'success',
      confirmIcon: 'mdi-sync'
    })

    if (!confirmed) return
  }

  bulkSyncing.value = true
  vmSyncResult.value = null

  try {
    const response = await api.post('/api/netbox/sync-vms', {
      vmids: selectedVMsToSync.value
    })
    vmSyncResult.value = response.data
    selectedVMsToSync.value = []

    // VMs neu scannen
    await scanProxmoxVMs()
  } catch (error) {
    console.error('Bulk sync failed:', error)
    vmSyncResult.value = {
      synced: 0,
      skipped: 0,
      errors: [error.response?.data?.detail || 'Unbekannter Fehler'],
      details: []
    }
  } finally {
    bulkSyncing.value = false
  }
}

// Bulk update ausgewaehlter registrierter VMs
async function bulkUpdateVMs() {
  if (selectedVMsToSync.value.length === 0) return

  // VMIDs aus Selection extrahieren (nur registrierte)
  const selectedItems = proxmoxVMs.value.filter(
    vm => selectedVMsToSync.value.includes(vm.vmid) && vm.status === 'registered'
  )
  const vmids = selectedItems.map(vm => vm.vmid).filter(Boolean)

  if (vmids.length === 0) return

  if (authStore.currentUiBeta) {
    const confirmed = await confirm({
      title: 'VMs aktualisieren?',
      message: `${vmids.length} VM(s) werden in NetBox aktualisiert.`,
      icon: 'mdi-refresh',
      iconColor: 'info',
      confirmLabel: 'Aktualisieren',
      confirmColor: 'info',
      confirmIcon: 'mdi-refresh'
    })

    if (!confirmed) return
  }

  bulkUpdating.value = true
  vmUpdateResult.value = null

  try {
    const response = await api.post('/api/netbox/update-vms', {
      vmids: vmids
    })
    vmUpdateResult.value = response.data
    selectedVMsToSync.value = []
  } catch (error) {
    console.error('Bulk update failed:', error)
    vmUpdateResult.value = {
      updated: 0,
      errors: [error.response?.data?.detail || 'Unbekannter Fehler'],
      details: []
    }
  } finally {
    bulkUpdating.value = false
  }
}

// Bestaetigung fuer Bulk-Delete
async function confirmBulkDelete() {
  if (selectedVMsToSync.value.length === 0) return

  // NetBox VM-IDs aus Selection extrahieren (nur orphaned)
  const selectedItems = proxmoxVMs.value.filter(
    vm => selectedVMsToSync.value.includes(vm.netbox_vm_id) && vm.status === 'orphaned'
  )
  const netboxVmIds = selectedItems.map(vm => vm.netbox_vm_id).filter(Boolean)

  if (netboxVmIds.length === 0) return

  if (authStore.currentUiBeta) {
    const confirmed = await confirm({
      title: 'Verwaiste VMs loeschen?',
      message: `${netboxVmIds.length} verwaiste VM(s) werden aus NetBox geloescht. Die zugehoerigen IP-Adressen werden freigegeben.`,
      icon: 'mdi-delete-alert',
      iconColor: 'error',
      confirmLabel: 'Alle loeschen',
      confirmColor: 'error',
      confirmIcon: 'mdi-delete',
      requireConfirmation: netboxVmIds.length > 1
    })

    if (!confirmed) return
  }

  await executeBulkDelete(netboxVmIds)
}

// Bulk-Delete ausfuehren
async function executeBulkDelete(netboxVmIds) {
  bulkDeleting.value = true
  bulkDeleteResult.value = null

  try {
    const response = await api.post('/api/netbox/delete-vms', {
      vm_ids: netboxVmIds
    })
    bulkDeleteResult.value = response.data
    selectedVMsToSync.value = []

    // VMs neu scannen
    await scanProxmoxVMs()
  } catch (error) {
    console.error('Bulk delete failed:', error)
    bulkDeleteResult.value = {
      deleted: 0,
      failed: netboxVmIds.length,
      errors: [error.response?.data?.detail || 'Unbekannter Fehler'],
      details: []
    }
  } finally {
    bulkDeleting.value = false
  }
}

// Beim Laden der Komponente
onMounted(async () => {
  // 1. Basis-Daten und Cache parallel laden
  await Promise.all([
    loadVlans(),
    loadPrefixes(),
    loadNetboxUrl(),
    loadCachedVlans(),
    loadCachedVMs()
  ])

  // 2. Auto-Scan im Hintergrund starten (aktualisiert Cache wenn Aenderungen)
  autoScanVlans()
  autoScanVMs()
})

// ==============================================
// Cache Functions
// ==============================================

const lastVlanScan = ref(null)
const lastVMScan = ref(null)
const vlanChanges = ref({ hasChanges: false, newVlans: [] })
const vmChanges = ref({ hasChanges: false, newVms: [], removedVms: [] })

// Gecachte VLANs laden
async function loadCachedVlans() {
  try {
    const response = await api.get('/api/netbox/cache/vlans')
    if (response.data.vlans?.length > 0) {
      proxmoxVlans.value = response.data.vlans.map(v => ({
        ...v,
        prefix: v.exists_in_netbox ? '' : `192.168.${v.vlan_id}.0/24`
      }))
      lastVlanScan.value = response.data.cached_at
      scannedOnce.value = true
      // Nur nicht-importierte VLANs vorauswaehlen
      selectedVlans.value = proxmoxVlans.value
        .filter(v => !v.exists_in_netbox)
        .map(v => v.vlan_id)
    }
  } catch (error) {
    console.log('Kein VLAN-Cache vorhanden')
  }
}

// Gecachte VMs laden
async function loadCachedVMs() {
  try {
    const response = await api.get('/api/netbox/cache/vms')
    if (response.data.vms?.length > 0) {
      proxmoxVMs.value = response.data.vms
      lastVMScan.value = response.data.cached_at
      // Nur nicht-registrierte VMs vorauswaehlen
      selectedVMsToSync.value = proxmoxVMs.value
        .filter(vm => vm.status === 'unregistered' && vm.vmid)
        .map(vm => vm.vmid)
    }
  } catch (error) {
    console.log('Kein VM-Cache vorhanden')
  }
}

// Auto-Scan VLANs (im Hintergrund)
async function autoScanVlans() {
  try {
    const response = await api.get('/api/netbox/proxmox-vlans')
    proxmoxVlans.value = response.data.vlans.map(v => ({
      ...v,
      prefix: v.exists_in_netbox ? '' : `192.168.${v.vlan_id}.0/24`
    }))
    lastVlanScan.value = response.data.cached_at
    scannedOnce.value = true
    vlanChanges.value = {
      hasChanges: response.data.has_changes,
      newVlans: response.data.new_vlans || []
    }
    // Nur nicht-importierte VLANs vorauswaehlen
    selectedVlans.value = proxmoxVlans.value
      .filter(v => !v.exists_in_netbox)
      .map(v => v.vlan_id)
  } catch (error) {
    console.error('Auto-Scan VLANs fehlgeschlagen:', error)
  }
}

// Auto-Scan VMs (im Hintergrund)
async function autoScanVMs() {
  try {
    const response = await api.get('/api/netbox/proxmox-vms')
    proxmoxVMs.value = response.data.vms
    lastVMScan.value = response.data.cached_at
    vmChanges.value = {
      hasChanges: response.data.has_changes,
      newVms: response.data.new_vms || [],
      removedVms: response.data.removed_vms || []
    }
    // Nur nicht-registrierte VMs vorauswaehlen
    selectedVMsToSync.value = proxmoxVMs.value
      .filter(vm => vm.status === 'unregistered' && vm.vmid)
      .map(vm => vm.vmid)
  } catch (error) {
    console.error('Auto-Scan VMs fehlgeschlagen:', error)
  }
}
</script>

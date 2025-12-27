<template>
  <v-container fluid class="pa-4">
    <div class="d-flex align-center mb-4">
      <v-icon size="large" class="mr-3">mdi-cog</v-icon>
      <div>
        <h1 class="text-h5">Einstellungen</h1>
        <p class="text-caption text-grey">System- und Verbindungseinstellungen</p>
      </div>
    </div>

    <v-row>
      <!-- Sidebar Navigation -->
      <v-col cols="12" md="2">
        <v-card>
          <v-list density="compact" nav>
            <v-list-item
              v-for="item in menuItems"
              :key="item.value"
              :value="item.value"
              :active="tab === item.value"
              :prepend-icon="item.icon"
              :title="item.title"
              @click="tab = item.value"
            />
          </v-list>
        </v-card>
      </v-col>

      <!-- Content Area -->
      <v-col cols="12" md="10">
        <v-tabs-window v-model="tab">
          <!-- Allgemein (User-spezifische Einstellungen via AuthStore) -->
          <v-tabs-window-item value="general">
            <v-card>
              <v-card-title>
                <v-icon start>mdi-palette</v-icon>
                Allgemeine Einstellungen
              </v-card-title>
              <v-card-text>
                <v-alert type="info" variant="tonal" density="compact" class="mb-4">
                  Diese Einstellungen gelten fuer Ihr Benutzerkonto.
                </v-alert>
                <v-row>
                  <v-col cols="12" md="6">
                    <div class="text-subtitle-2 mb-3">Erscheinungsbild</div>
                    <v-btn-toggle
                      v-model="userSettings.dark_mode"
                      mandatory
                      density="compact"
                      class="mb-4"
                    >
                      <v-btn value="light" size="small">
                        <v-icon start>mdi-white-balance-sunny</v-icon>
                        Hell
                      </v-btn>
                      <v-btn value="system" size="small">
                        <v-icon start>mdi-theme-light-dark</v-icon>
                        System
                      </v-btn>
                      <v-btn value="dark" size="small">
                        <v-icon start>mdi-weather-night</v-icon>
                        Dunkel
                      </v-btn>
                    </v-btn-toggle>

                    <div class="text-subtitle-2 mb-3">Farbschema</div>
                    <div class="d-flex gap-2">
                      <v-btn
                        v-for="t in availableThemes"
                        :key="t.value"
                        icon
                        size="small"
                        :color="t.color"
                        :variant="userSettings.theme === t.value ? 'flat' : 'outlined'"
                        @click="userSettings.theme = t.value"
                      >
                        <v-icon v-if="userSettings.theme === t.value" size="16">mdi-check</v-icon>
                      </v-btn>
                    </div>
                  </v-col>
                  <v-col cols="12" md="6">
                    <div class="text-subtitle-2 mb-3">Features</div>
                    <v-checkbox
                      v-model="userSettings.ui_beta"
                      label="Beta-UI aktivieren"
                      hint="Neue UI-Komponenten und Features testen"
                      persistent-hint
                      density="compact"
                    />
                  </v-col>
                </v-row>
              </v-card-text>
              <v-card-actions>
                <v-spacer />
                <v-btn color="primary" :loading="saving" @click="saveGeneral">
                  Speichern
                </v-btn>
              </v-card-actions>
            </v-card>
          </v-tabs-window-item>

          <!-- Sicherheit -->
          <v-tabs-window-item value="security">
            <v-card>
              <v-card-title class="d-flex align-center">
                <v-icon start>mdi-shield-check</v-icon>
                Sicherheitsstatus
                <v-spacer />
                <v-chip
                  :color="securityStatus.overall_status === 'secure' ? 'success' : securityStatus.overall_status === 'warnings' ? 'warning' : 'error'"
                  size="small"
                  variant="flat"
                >
                  <v-icon start size="small">
                    {{ securityStatus.overall_status === 'secure' ? 'mdi-check-circle' : securityStatus.overall_status === 'warnings' ? 'mdi-alert' : 'mdi-alert-circle' }}
                  </v-icon>
                  {{ securityStatus.overall_status === 'secure' ? 'Sicher' : securityStatus.overall_status === 'warnings' ? 'Warnungen' : 'Probleme' }}
                </v-chip>
              </v-card-title>
              <v-card-text>
                <v-alert type="info" variant="tonal" density="compact" class="mb-4">
                  Uebersicht der Sicherheitskonfiguration. Aenderungen erfolgen ueber die .env Datei oder docker-compose.yml.
                </v-alert>

                <v-list v-if="!loadingSecurityStatus" density="compact" class="border rounded">
                  <v-list-item
                    v-for="item in securityStatus.items"
                    :key="item.name"
                    :class="{ 'bg-error-lighten-5': item.status === 'error', 'bg-warning-lighten-5': item.status === 'warning' }"
                  >
                    <template v-slot:prepend>
                      <v-icon
                        :color="item.status === 'ok' ? 'success' : item.status === 'warning' ? 'warning' : item.status === 'error' ? 'error' : 'info'"
                      >
                        {{ item.status === 'ok' ? 'mdi-check-circle' : item.status === 'warning' ? 'mdi-alert' : item.status === 'error' ? 'mdi-alert-circle' : 'mdi-information' }}
                      </v-icon>
                    </template>
                    <v-list-item-title class="font-weight-medium">{{ item.name }}</v-list-item-title>
                    <v-list-item-subtitle>
                      {{ item.message }}
                      <span v-if="item.details" class="text-caption text-grey ml-2">({{ item.details }})</span>
                    </v-list-item-subtitle>
                  </v-list-item>
                </v-list>

                <v-skeleton-loader v-else type="list-item@8" />
              </v-card-text>
              <v-card-actions>
                <v-btn variant="outlined" size="small" @click="loadSecurityStatus" :loading="loadingSecurityStatus">
                  <v-icon start>mdi-refresh</v-icon>
                  Aktualisieren
                </v-btn>
              </v-card-actions>
            </v-card>
          </v-tabs-window-item>

          <!-- Proxmox -->
          <v-tabs-window-item value="proxmox">
            <v-card>
              <v-card-title>
                <v-icon start>mdi-server</v-icon>
                Proxmox Verbindung
              </v-card-title>
              <v-card-text>
                <v-alert type="info" variant="tonal" density="compact" class="mb-4">
                  Verbindung zum Proxmox VE Cluster konfigurieren.
                </v-alert>
                <v-row>
                  <v-col cols="12" md="8">
                    <v-text-field
                      v-model="proxmox.proxmox_host"
                      label="Host (IP oder URL)"
                      placeholder="192.168.1.100 oder https://proxmox.example.com"
                      variant="outlined"
                      density="compact"
                      hint="Ohne Port: 8006 wird automatisch verwendet"
                    />
                  </v-col>
                  <v-col cols="12" md="4">
                    <v-checkbox
                      v-model="proxmox.proxmox_verify_ssl"
                      label="SSL verifizieren"
                      density="compact"
                      hide-details
                    />
                  </v-col>
                  <v-col cols="12" md="6">
                    <v-text-field
                      v-model="proxmox.proxmox_token_id"
                      label="Token ID"
                      placeholder="terraform@pve!terraform-token"
                      variant="outlined"
                      density="compact"
                    />
                  </v-col>
                  <v-col cols="12" md="6">
                    <v-text-field
                      v-model="proxmox.proxmox_token_secret"
                      label="Token Secret"
                      type="password"
                      variant="outlined"
                      density="compact"
                    />
                  </v-col>
                </v-row>
              </v-card-text>
              <v-card-actions>
                <v-btn variant="outlined" @click="testProxmox" :loading="testing">
                  <v-icon start>mdi-connection</v-icon>
                  Verbindung testen
                </v-btn>
                <v-spacer />
                <v-btn color="primary" :loading="saving" @click="saveProxmox">
                  Speichern
                </v-btn>
              </v-card-actions>
            </v-card>
          </v-tabs-window-item>

          <!-- NetBox -->
          <v-tabs-window-item value="netbox">
            <v-card>
              <v-card-title class="d-flex align-center">
                <v-icon start>mdi-database</v-icon>
                NetBox Einstellungen
                <v-spacer />
                <v-btn
                  v-if="netboxUrl"
                  variant="text"
                  size="small"
                  :href="netboxUrl"
                  target="_blank"
                >
                  <v-icon start>mdi-open-in-new</v-icon>
                  NetBox oeffnen
                </v-btn>
              </v-card-title>
              <v-card-text>
                <v-alert type="info" variant="tonal" density="compact" class="mb-4">
                  Externe NetBox URL fuer Frontend-Links konfigurieren.
                  Die interne NetBox-Instanz ist automatisch verbunden.
                </v-alert>
                <v-row>
                  <v-col cols="12">
                    <v-text-field
                      v-model="netboxUrl"
                      label="Externe NetBox URL"
                      placeholder="https://netbox.example.com oder http://192.168.1.100:8080"
                      variant="outlined"
                      density="compact"
                      hint="URL ueber die NetBox im Browser erreichbar ist"
                    />
                  </v-col>
                </v-row>
              </v-card-text>
              <v-card-actions>
                <v-spacer />
                <v-btn color="primary" :loading="saving" @click="saveNetbox">
                  Speichern
                </v-btn>
              </v-card-actions>
            </v-card>
          </v-tabs-window-item>

          <!-- SSH/Ansible -->
          <v-tabs-window-item value="ansible">
            <v-card>
              <v-card-title>
                <v-icon start>mdi-ansible</v-icon>
                SSH Konfiguration
              </v-card-title>
              <v-card-text>
                <v-alert type="info" variant="tonal" density="compact" class="mb-4">
                  SSH-Benutzer fuer Ansible-Verbindungen.
                </v-alert>
                <v-row>
                  <v-col cols="12" md="6">
                    <v-text-field
                      v-model="sshConfig.ssh_user"
                      label="SSH Benutzer"
                      placeholder="ansible"
                      variant="outlined"
                      density="compact"
                    />
                  </v-col>
                  <v-col cols="12" md="6">
                    <v-text-field
                      v-model="sshConfig.active_key"
                      label="Aktiver SSH Key"
                      variant="outlined"
                      density="compact"
                      readonly
                      hint="Wird ueber SSH-Keys verwaltet"
                    />
                  </v-col>
                </v-row>
                <v-btn variant="outlined" class="mt-2" @click="sshKeyDialog = true">
                  <v-icon start>mdi-key</v-icon>
                  SSH-Keys verwalten
                </v-btn>
              </v-card-text>
              <v-card-actions>
                <v-spacer />
                <v-btn color="primary" :loading="saving" @click="saveSsh">
                  Speichern
                </v-btn>
              </v-card-actions>
            </v-card>
          </v-tabs-window-item>

          <!-- Cloud-Init -->
          <v-tabs-window-item value="cloudinit">
            <CloudInitSettings />
          </v-tabs-window-item>

          <!-- Notifications -->
          <v-tabs-window-item value="notifications">
            <v-card>
              <v-card-title>
                <v-icon start>mdi-bell</v-icon>
                Globale Benachrichtigungen
              </v-card-title>
              <v-card-text>
                <v-row>
                  <!-- Gotify -->
                  <v-col cols="12" md="6">
                    <div class="text-subtitle-2 mb-3">
                      <v-icon start size="small">mdi-bell-ring</v-icon>
                      Gotify
                    </div>
                    <v-switch
                      v-model="notifications.gotify_enabled"
                      label="Gotify aktivieren"
                      density="compact"
                      color="primary"
                      hide-details
                      class="mb-2"
                    />
                    <v-text-field
                      v-model="notifications.gotify_url"
                      label="Server URL"
                      placeholder="https://gotify.example.com"
                      variant="outlined"
                      density="compact"
                      :disabled="!notifications.gotify_enabled"
                    />
                    <v-text-field
                      v-model="notifications.gotify_token"
                      label="App Token"
                      type="password"
                      variant="outlined"
                      density="compact"
                      :disabled="!notifications.gotify_enabled"
                    />
                    <v-slider
                      v-model="notifications.gotify_priority"
                      label="Prioritaet"
                      :min="1"
                      :max="10"
                      :step="1"
                      thumb-label
                      density="compact"
                      :disabled="!notifications.gotify_enabled"
                    />
                  </v-col>

                  <!-- SMTP -->
                  <v-col cols="12" md="6">
                    <div class="text-subtitle-2 mb-3">
                      <v-icon start size="small">mdi-email</v-icon>
                      E-Mail (SMTP)
                    </div>
                    <v-switch
                      v-model="notifications.smtp_enabled"
                      label="SMTP aktivieren"
                      density="compact"
                      color="primary"
                      hide-details
                      class="mb-2"
                    />
                    <v-text-field
                      v-model="notifications.smtp_host"
                      label="SMTP Server"
                      placeholder="smtp.example.com"
                      variant="outlined"
                      density="compact"
                      :disabled="!notifications.smtp_enabled"
                    />
                    <v-row dense>
                      <v-col cols="6">
                        <v-text-field
                          v-model="notifications.smtp_port"
                          label="Port"
                          type="number"
                          variant="outlined"
                          density="compact"
                          :disabled="!notifications.smtp_enabled"
                        />
                      </v-col>
                      <v-col cols="6">
                        <v-select
                          v-model="smtpSecurity"
                          :items="['Keine', 'STARTTLS', 'SSL/TLS']"
                          label="Sicherheit"
                          variant="outlined"
                          density="compact"
                          :disabled="!notifications.smtp_enabled"
                        />
                      </v-col>
                    </v-row>
                    <v-text-field
                      v-model="notifications.smtp_user"
                      label="Benutzername"
                      variant="outlined"
                      density="compact"
                      :disabled="!notifications.smtp_enabled"
                    />
                    <v-text-field
                      v-model="notifications.smtp_password"
                      label="Passwort"
                      type="password"
                      variant="outlined"
                      density="compact"
                      :disabled="!notifications.smtp_enabled"
                      :placeholder="notifications.smtp_password_set ? '(gespeichert)' : ''"
                    />
                    <v-text-field
                      v-model="notifications.smtp_from_email"
                      label="Absender E-Mail"
                      placeholder="noreply@example.com"
                      variant="outlined"
                      density="compact"
                      :disabled="!notifications.smtp_enabled"
                    />
                    <v-text-field
                      v-model="notifications.smtp_from_name"
                      label="Absender Name"
                      placeholder="PVE Commander"
                      variant="outlined"
                      density="compact"
                      :disabled="!notifications.smtp_enabled"
                    />
                  </v-col>
                </v-row>
              </v-card-text>
              <v-card-actions>
                <v-btn
                  variant="outlined"
                  @click="testGotify"
                  :loading="testing"
                  :disabled="!notifications.gotify_enabled"
                >
                  <v-icon start>mdi-bell-ring</v-icon>
                  Gotify testen
                </v-btn>
                <v-btn
                  variant="outlined"
                  @click="testSmtp"
                  :loading="testingSmtp"
                  :disabled="!notifications.smtp_enabled"
                >
                  <v-icon start>mdi-email-check</v-icon>
                  E-Mail testen
                </v-btn>
                <v-spacer />
                <v-btn color="primary" :loading="saving" @click="saveNotifications">
                  Speichern
                </v-btn>
              </v-card-actions>
            </v-card>
          </v-tabs-window-item>

          <!-- Backup -->
          <v-tabs-window-item value="backup">
            <v-card>
              <v-card-title class="pb-2">
                <v-icon start>mdi-backup-restore</v-icon>
                Backup & Restore
              </v-card-title>
              <v-card-text class="pt-0">
                <v-row>
                  <!-- Manuelles Backup -->
                  <v-col cols="12" md="6">
                    <div class="text-subtitle-2 mb-2">Manuelles Backup</div>
                    <div class="d-flex gap-2">
                      <v-btn color="primary" size="small" @click="createBackup" :loading="backupLoading">
                        <v-icon start size="small">mdi-cloud-download</v-icon>
                        Erstellen
                      </v-btn>
                      <v-btn variant="outlined" size="small" @click="openRestoreDialog">
                        <v-icon start size="small">mdi-cloud-upload</v-icon>
                        Wiederherstellen
                      </v-btn>
                    </div>
                    <!-- Backup Liste -->
                    <v-list v-if="backups.length > 0" density="compact" class="border rounded mt-2 py-0">
                      <v-list-item
                        v-for="backup in backups.slice(0, 3)"
                        :key="backup.id"
                        density="compact"
                      >
                        <v-list-item-title class="text-caption">{{ backup.filename }}</v-list-item-title>
                        <v-list-item-subtitle class="text-caption">{{ formatBackupDate(backup.created_at) }}</v-list-item-subtitle>
                        <template v-slot:append>
                          <v-btn icon size="x-small" variant="text" @click="downloadBackup(backup.id)">
                            <v-icon size="16">mdi-download</v-icon>
                          </v-btn>
                        </template>
                      </v-list-item>
                    </v-list>
                  </v-col>

                  <!-- Zeitgesteuerte Backups -->
                  <v-col cols="12" md="6">
                    <div class="text-subtitle-2 mb-2">Automatische Backups</div>
                    <v-switch
                      v-model="backupSchedule.enabled"
                      label="Aktivieren"
                      color="primary"
                      density="compact"
                      hide-details
                      class="mb-2"
                    />
                    <v-row v-if="backupSchedule.enabled" dense>
                      <v-col cols="4">
                        <v-select
                          v-model="backupSchedule.frequency"
                          :items="[
                            { title: 'Taeglich', value: 'daily' },
                            { title: 'Woechentlich', value: 'weekly' }
                          ]"
                          item-title="title"
                          item-value="value"
                          label="Intervall"
                          variant="outlined"
                          density="compact"
                          hide-details
                        />
                      </v-col>
                      <v-col cols="4">
                        <v-text-field
                          v-model="backupSchedule.time"
                          type="time"
                          label="Uhrzeit"
                          variant="outlined"
                          density="compact"
                          hide-details
                        />
                      </v-col>
                      <v-col cols="4">
                        <v-text-field
                          v-model.number="backupSchedule.retention_days"
                          type="number"
                          :min="1"
                          :max="365"
                          label="Tage"
                          variant="outlined"
                          density="compact"
                          hide-details
                        />
                      </v-col>
                    </v-row>
                    <div v-if="backupSchedule.enabled && backupSchedule.next_run" class="text-caption text-grey mt-2">
                      Naechstes: {{ formatBackupDate(backupSchedule.next_run) }}
                    </div>
                  </v-col>
                </v-row>
              </v-card-text>
              <v-card-actions v-if="backupSchedule.enabled" class="pt-0">
                <v-spacer />
                <v-btn color="primary" :loading="savingSchedule" @click="saveSchedule">
                  Zeitplan speichern
                </v-btn>
              </v-card-actions>
            </v-card>
          </v-tabs-window-item>

          <!-- Users -->
          <v-tabs-window-item value="users">
            <UsersManager />
          </v-tabs-window-item>

          <!-- Roles -->
          <v-tabs-window-item value="roles">
            <RolesManager />
          </v-tabs-window-item>
        </v-tabs-window>
      </v-col>
    </v-row>

    <!-- SSH Key Management Dialog -->
    <v-dialog v-model="sshKeyDialog" max-width="700">
      <v-card>
        <v-card-title>
          <v-icon start>mdi-key</v-icon>
          SSH-Keys verwalten
        </v-card-title>
        <v-card-text>
          <v-alert type="info" variant="tonal" density="compact" class="mb-4">
            SSH-Keys werden fuer Ansible-Verbindungen zu VMs benoetigt.
            Laden Sie Ihren <strong>Private Key</strong> hoch (z.B. id_ed25519 oder id_rsa).
          </v-alert>

          <!-- Gespeicherte Keys -->
          <div v-if="sshKeyData.stored_keys?.length > 0" class="mb-4">
            <div class="text-subtitle-2 mb-2">Gespeicherte Keys</div>
            <v-list density="compact" class="border rounded">
              <v-list-item
                v-for="key in sshKeyData.stored_keys"
                :key="key.id || key.name"
                :title="key.name"
                :subtitle="key.type + (key.fingerprint ? ' - ' + key.fingerprint : '')"
              >
                <template v-slot:prepend>
                  <v-icon :color="key.is_active ? 'success' : 'grey'">
                    {{ key.is_active ? 'mdi-key-check' : 'mdi-key' }}
                  </v-icon>
                </template>
                <template v-slot:append>
                  <v-chip v-if="key.is_active" size="x-small" color="success" class="mr-2">
                    Aktiv
                  </v-chip>
                  <v-btn
                    v-else
                    variant="text"
                    size="small"
                    color="primary"
                    @click="activateSshKey(key.id || key.name)"
                  >
                    Aktivieren
                  </v-btn>
                </template>
              </v-list-item>
            </v-list>
          </div>

          <!-- Host Keys (zum Import) -->
          <div v-if="sshKeyData.keys?.length > 0" class="mb-4">
            <div class="text-subtitle-2 mb-2">Verfuegbare Keys vom Host</div>
            <v-list density="compact" class="border rounded">
              <v-list-item
                v-for="key in sshKeyData.keys"
                :key="key.path"
                :title="key.name"
                :subtitle="key.type"
              >
                <template v-slot:prepend>
                  <v-icon color="grey">mdi-key-outline</v-icon>
                </template>
                <template v-slot:append>
                  <v-btn
                    variant="text"
                    size="small"
                    @click="importSshKey(key.path)"
                  >
                    Importieren
                  </v-btn>
                </template>
              </v-list-item>
            </v-list>
          </div>

          <!-- Kein Key vorhanden -->
          <v-alert
            v-if="!sshKeyData.stored_keys?.length && !sshKeyData.keys?.length"
            type="warning"
            variant="tonal"
          >
            Keine SSH-Keys gefunden. Laden Sie einen Private Key hoch.
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-btn variant="outlined" @click="showUploadKeyDialog = true">
            <v-icon start>mdi-upload</v-icon>
            Key hochladen
          </v-btn>
          <v-btn variant="outlined" @click="showGenerateKeyDialog = true">
            <v-icon start>mdi-plus</v-icon>
            Key generieren
          </v-btn>
          <v-spacer />
          <v-btn variant="text" @click="sshKeyDialog = false">Schliessen</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- SSH Key Upload Dialog -->
    <v-dialog v-model="showUploadKeyDialog" max-width="600">
      <v-card>
        <v-card-title>
          <v-icon start>mdi-upload</v-icon>
          SSH Private Key hochladen
        </v-card-title>
        <v-card-text>
          <v-alert type="info" variant="tonal" density="compact" class="mb-4">
            Fuegen Sie den Inhalt Ihres <strong>Private Keys</strong> ein (z.B. aus ~/.ssh/id_ed25519).
            Der Public Key wird automatisch generiert.
          </v-alert>
          <v-text-field
            v-model="uploadKey.name"
            label="Key-Name (optional)"
            placeholder="mein-ansible-key"
            variant="outlined"
            density="compact"
            hint="Leer lassen fuer automatischen Namen"
            class="mb-2"
          />
          <v-textarea
            v-model="uploadKey.private_key"
            label="Private Key"
            placeholder="-----BEGIN OPENSSH PRIVATE KEY-----
...
-----END OPENSSH PRIVATE KEY-----"
            variant="outlined"
            rows="8"
            class="font-monospace"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showUploadKeyDialog = false">Abbrechen</v-btn>
          <v-btn
            color="primary"
            :loading="uploadingKey"
            :disabled="!uploadKey.private_key"
            @click="uploadSshKey"
          >
            Hochladen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- SSH Key Generate Dialog -->
    <v-dialog v-model="showGenerateKeyDialog" max-width="500">
      <v-card>
        <v-card-title>
          <v-icon start>mdi-plus</v-icon>
          Neuen SSH Key generieren
        </v-card-title>
        <v-card-text>
          <v-alert type="info" variant="tonal" density="compact" class="mb-4">
            Ein neues Schluesselpaar wird generiert. Der Public Key muss auf den Ziel-VMs hinterlegt werden.
          </v-alert>
          <v-text-field
            v-model="generateKey.name"
            label="Key-Name (optional)"
            placeholder="ansible-key"
            variant="outlined"
            density="compact"
            class="mb-2"
          />
          <v-select
            v-model="generateKey.type"
            :items="[
              { title: 'Ed25519 (empfohlen)', value: 'ed25519' },
              { title: 'RSA 4096', value: 'rsa' }
            ]"
            label="Key-Typ"
            variant="outlined"
            density="compact"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="showGenerateKeyDialog = false">Abbrechen</v-btn>
          <v-btn
            color="primary"
            :loading="generatingKey"
            @click="generateSshKey"
          >
            Generieren
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Public Key Anzeige Dialog -->
    <v-dialog v-model="showPublicKeyDialog" max-width="600">
      <v-card>
        <v-card-title>
          <v-icon start color="success">mdi-check-circle</v-icon>
          SSH Key erstellt
        </v-card-title>
        <v-card-text>
          <v-alert type="success" variant="tonal" density="compact" class="mb-4">
            Der Key wurde erfolgreich erstellt. Kopieren Sie den Public Key und fuegen Sie ihn
            auf Ihren Ziel-VMs in <code>~/.ssh/authorized_keys</code> ein.
          </v-alert>
          <v-textarea
            v-model="generatedPublicKey"
            label="Public Key"
            readonly
            variant="outlined"
            rows="4"
            class="font-monospace"
          />
        </v-card-text>
        <v-card-actions>
          <v-btn variant="outlined" @click="copyPublicKey">
            <v-icon start>mdi-content-copy</v-icon>
            Kopieren
          </v-btn>
          <v-spacer />
          <v-btn color="primary" @click="showPublicKeyDialog = false">Schliessen</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Restore Dialog -->
    <v-dialog v-model="restoreDialog" max-width="500">
      <v-card>
        <v-card-title>
          <v-icon start>mdi-cloud-upload</v-icon>
          Backup wiederherstellen
        </v-card-title>
        <v-card-text>
          <v-alert type="warning" variant="tonal" density="compact" class="mb-4">
            Das Wiederherstellen ueberschreibt die aktuellen Daten!
          </v-alert>
          <v-file-input
            v-model="restoreFile"
            label="Backup-Datei (ZIP)"
            accept=".zip"
            variant="outlined"
            density="compact"
            prepend-icon="mdi-file-upload"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="restoreDialog = false">Abbrechen</v-btn>
          <v-btn
            color="warning"
            :loading="restoring"
            :disabled="!restoreFile"
            @click="restoreBackup"
          >
            Wiederherstellen
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted, inject } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import api from '@/api/client'
import UsersManager from '@/components/UsersManager.vue'
import RolesManager from '@/components/RolesManager.vue'
import CloudInitSettings from '@/components/settings/CloudInitSettings.vue'

const route = useRoute()
const authStore = useAuthStore()
const showSnackbar = inject('showSnackbar')

const tab = ref('general')
const saving = ref(false)
const testing = ref(false)
const testingSmtp = ref(false)
const backupLoading = ref(false)
const restoring = ref(false)
const sshKeyDialog = ref(false)
const restoreDialog = ref(false)
const restoreFile = ref(null)
const backups = ref([])
const savingSchedule = ref(false)
const backupSchedule = ref({
  enabled: false,
  frequency: 'daily',
  time: '02:00',
  retention_days: 7,
  last_run: null,
  next_run: null,
})

// Security Status
const securityStatus = ref({ overall_status: 'secure', items: [] })
const loadingSecurityStatus = ref(false)

// SSH Key Management
const sshKeyData = ref({ keys: [], stored_keys: [], current_key: null })
const showUploadKeyDialog = ref(false)
const showGenerateKeyDialog = ref(false)
const showPublicKeyDialog = ref(false)
const uploadingKey = ref(false)
const generatingKey = ref(false)
const generatedPublicKey = ref('')
const uploadKey = ref({ name: '', private_key: '' })
const generateKey = ref({ name: '', type: 'ed25519' })

const menuItems = [
  { value: 'general', title: 'Allgemein', icon: 'mdi-palette' },
  { value: 'security', title: 'Sicherheit', icon: 'mdi-shield-check' },
  { value: 'proxmox', title: 'Proxmox', icon: 'mdi-server' },
  { value: 'netbox', title: 'NetBox', icon: 'mdi-database' },
  { value: 'ansible', title: 'SSH/Ansible', icon: 'mdi-ansible' },
  { value: 'cloudinit', title: 'Cloud-Init', icon: 'mdi-cloud-cog' },
  { value: 'notifications', title: 'Benachrichtigungen', icon: 'mdi-bell' },
  { value: 'backup', title: 'Backup', icon: 'mdi-backup-restore' },
  { value: 'users', title: 'Benutzer', icon: 'mdi-account-group' },
  { value: 'roles', title: 'Rollen', icon: 'mdi-shield-account' },
]

// Verfuegbare Farbthemes
const availableThemes = [
  { value: 'blue', color: '#1976D2' },
  { value: 'orange', color: '#FB8C00' },
  { value: 'green', color: '#43A047' },
  { value: 'purple', color: '#8E24AA' },
  { value: 'teal', color: '#00897B' },
]

// User-spezifische Einstellungen (via AuthStore)
const userSettings = ref({
  theme: 'blue',
  dark_mode: 'system',
  ui_beta: false,
})

// Proxmox Einstellungen
const proxmox = ref({
  proxmox_host: '',
  proxmox_token_id: '',
  proxmox_token_secret: '',
  proxmox_verify_ssl: false,
})

// NetBox URL
const netboxUrl = ref('')

// SSH Config
const sshConfig = ref({
  ssh_user: '',
  active_key: '',
})

// Notifications
const notifications = ref({
  gotify_enabled: false,
  gotify_url: '',
  gotify_token: '',
  gotify_priority: 5,
  smtp_enabled: false,
  smtp_host: '',
  smtp_port: 587,
  smtp_user: '',
  smtp_password: '',
  smtp_password_set: false,
  smtp_from_email: '',
  smtp_from_name: '',
  smtp_use_tls: true,
  smtp_use_ssl: false,
})

// Computed fuer SMTP Security Dropdown
const smtpSecurity = computed({
  get() {
    if (notifications.value.smtp_use_ssl) return 'SSL/TLS'
    if (notifications.value.smtp_use_tls) return 'STARTTLS'
    return 'Keine'
  },
  set(val) {
    notifications.value.smtp_use_ssl = val === 'SSL/TLS'
    notifications.value.smtp_use_tls = val === 'STARTTLS'
  }
})

async function loadSettings() {
  try {
    // User Settings aus AuthStore
    userSettings.value.theme = authStore.currentTheme || 'blue'
    userSettings.value.dark_mode = authStore.currentDarkMode || 'system'
    userSettings.value.ui_beta = authStore.currentUiBeta || false

    // Proxmox laden
    const proxmoxRes = await api.get('/api/settings/proxmox').catch(() => ({ data: {} }))
    if (proxmoxRes.data) {
      proxmox.value = {
        proxmox_host: proxmoxRes.data.proxmox_host || '',
        proxmox_token_id: proxmoxRes.data.proxmox_token_id || '',
        proxmox_token_secret: proxmoxRes.data.proxmox_token_secret || '',
        proxmox_verify_ssl: proxmoxRes.data.proxmox_verify_ssl || false,
      }
    }

    // NetBox URL laden
    const netboxRes = await api.get('/api/settings/netbox-url').catch(() => ({ data: {} }))
    netboxUrl.value = netboxRes.data?.url || ''

    // SSH Config laden
    const sshRes = await api.get('/api/settings/ssh').catch(() => ({ data: {} }))
    if (sshRes.data) {
      sshConfig.value = {
        ssh_user: sshRes.data.ssh_user || '',
        active_key: sshRes.data.active_key || '',
      }
    }

    // Notifications laden
    const notifyRes = await api.get('/api/notifications/settings').catch(() => ({ data: {} }))
    if (notifyRes.data) {
      notifications.value = {
        gotify_enabled: notifyRes.data.gotify_enabled || false,
        gotify_url: notifyRes.data.gotify_url || '',
        gotify_token: '', // Token nie vom Backend zurueckgeben
        gotify_priority: notifyRes.data.gotify_priority || 5,
        smtp_enabled: notifyRes.data.smtp_enabled || false,
        smtp_host: notifyRes.data.smtp_host || '',
        smtp_port: notifyRes.data.smtp_port || 587,
        smtp_user: notifyRes.data.smtp_user || '',
        smtp_password: '', // Passwort nie vom Backend zurueckgeben
        smtp_password_set: notifyRes.data.smtp_password_set || false,
        smtp_from_email: notifyRes.data.smtp_from_email || '',
        smtp_from_name: notifyRes.data.smtp_from_name || '',
        smtp_use_tls: notifyRes.data.smtp_use_tls ?? true,
        smtp_use_ssl: notifyRes.data.smtp_use_ssl ?? false,
      }
    }

    // Backups und Schedule laden
    await loadBackups()
    await loadSchedule()
  } catch (e) {
    console.error('Settings laden fehlgeschlagen:', e)
  }
}

async function loadSecurityStatus() {
  loadingSecurityStatus.value = true
  try {
    const res = await api.get('/api/settings/security-status')
    securityStatus.value = res.data || { overall_status: 'secure', items: [] }
  } catch {
    securityStatus.value = { overall_status: 'secure', items: [] }
  } finally {
    loadingSecurityStatus.value = false
  }
}

async function loadBackups() {
  try {
    const res = await api.get('/api/backup/list')
    backups.value = res.data || []
  } catch {
    backups.value = []
  }
}

async function loadSchedule() {
  try {
    const res = await api.get('/api/backup/schedule')
    if (res.data) {
      backupSchedule.value = {
        enabled: res.data.enabled || false,
        frequency: res.data.frequency || 'daily',
        time: res.data.time || '02:00',
        retention_days: res.data.retention_days || 7,
        last_run: res.data.last_run,
        next_run: res.data.next_run,
      }
    }
  } catch {
    // Schedule nicht verfuegbar
  }
}

async function saveSchedule() {
  savingSchedule.value = true
  try {
    const res = await api.put('/api/backup/schedule', {
      enabled: backupSchedule.value.enabled,
      frequency: backupSchedule.value.frequency,
      time: backupSchedule.value.time,
      retention_days: backupSchedule.value.retention_days,
    })
    if (res.data) {
      backupSchedule.value.next_run = res.data.next_run
      backupSchedule.value.last_run = res.data.last_run
    }
    showSnackbar?.('Backup-Zeitplan gespeichert', 'success')
  } catch (e) {
    showSnackbar?.('Speichern fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    savingSchedule.value = false
  }
}

async function saveGeneral() {
  saving.value = true
  try {
    // Verwende updatePreferences aus authStore
    await authStore.updatePreferences(
      userSettings.value.theme,
      userSettings.value.dark_mode,
      null, // sidebarLogo bleibt
      userSettings.value.ui_beta
    )
    showSnackbar?.('Einstellungen gespeichert', 'success')
  } catch (e) {
    showSnackbar?.('Speichern fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    saving.value = false
  }
}

async function saveProxmox() {
  saving.value = true
  try {
    await api.put('/api/settings/proxmox', proxmox.value)
    showSnackbar?.('Proxmox-Einstellungen gespeichert', 'success')
  } catch (e) {
    showSnackbar?.('Speichern fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    saving.value = false
  }
}

async function testProxmox() {
  testing.value = true
  try {
    const response = await api.post('/api/settings/proxmox/test', {
      host: proxmox.value.proxmox_host,
      token_id: proxmox.value.proxmox_token_id,
      token_secret: proxmox.value.proxmox_token_secret,
      verify_ssl: proxmox.value.proxmox_verify_ssl,
    })
    if (response.data.success) {
      showSnackbar?.(`Verbindung erfolgreich - ${response.data.version || 'OK'}`, 'success')
    } else {
      showSnackbar?.('Verbindung fehlgeschlagen: ' + response.data.message, 'error')
    }
  } catch (e) {
    showSnackbar?.('Verbindung fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    testing.value = false
  }
}

async function saveNetbox() {
  saving.value = true
  try {
    await api.put('/api/settings/netbox-url', { url: netboxUrl.value })
    showSnackbar?.('NetBox-URL gespeichert', 'success')
  } catch (e) {
    showSnackbar?.('Speichern fehlgeschlagen', 'error')
  } finally {
    saving.value = false
  }
}

async function saveSsh() {
  saving.value = true
  try {
    await api.put('/api/settings/ssh', { ssh_user: sshConfig.value.ssh_user })
    showSnackbar?.('SSH-Einstellungen gespeichert', 'success')
  } catch (e) {
    showSnackbar?.('Speichern fehlgeschlagen', 'error')
  } finally {
    saving.value = false
  }
}

async function loadSshKeys() {
  try {
    const res = await api.get('/api/settings/ssh/keys')
    sshKeyData.value = res.data || { keys: [], stored_keys: [], current_key: null }
  } catch {
    sshKeyData.value = { keys: [], stored_keys: [], current_key: null }
  }
}

async function activateSshKey(keyId) {
  try {
    await api.post('/api/settings/ssh/activate', { key_id: keyId })
    showSnackbar?.('SSH-Key aktiviert', 'success')
    await loadSshKeys()
    await loadSettings()
  } catch (e) {
    showSnackbar?.('Aktivierung fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

async function importSshKey(sourcePath) {
  try {
    const res = await api.post('/api/settings/ssh/import', { source_path: sourcePath })
    if (res.data.success) {
      showSnackbar?.('SSH-Key importiert', 'success')
      if (res.data.public_key) {
        generatedPublicKey.value = res.data.public_key
        showPublicKeyDialog.value = true
      }
      await loadSshKeys()
    } else {
      showSnackbar?.('Import fehlgeschlagen: ' + res.data.message, 'error')
    }
  } catch (e) {
    showSnackbar?.('Import fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

async function uploadSshKey() {
  uploadingKey.value = true
  try {
    const res = await api.post('/api/settings/ssh/upload', {
      private_key: uploadKey.value.private_key,
      key_name: uploadKey.value.name || undefined,
    })
    if (res.data.success) {
      showSnackbar?.('SSH-Key hochgeladen', 'success')
      showUploadKeyDialog.value = false
      uploadKey.value = { name: '', private_key: '' }
      if (res.data.public_key) {
        generatedPublicKey.value = res.data.public_key
        showPublicKeyDialog.value = true
      }
      await loadSshKeys()
    } else {
      showSnackbar?.('Upload fehlgeschlagen: ' + res.data.message, 'error')
    }
  } catch (e) {
    showSnackbar?.('Upload fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    uploadingKey.value = false
  }
}

async function generateSshKey() {
  generatingKey.value = true
  try {
    const res = await api.post('/api/settings/ssh/generate', {
      key_type: generateKey.value.type,
      key_name: generateKey.value.name || undefined,
    })
    if (res.data.success) {
      showSnackbar?.('SSH-Key generiert', 'success')
      showGenerateKeyDialog.value = false
      generateKey.value = { name: '', type: 'ed25519' }
      if (res.data.public_key) {
        generatedPublicKey.value = res.data.public_key
        showPublicKeyDialog.value = true
      }
      await loadSshKeys()
    } else {
      showSnackbar?.('Generierung fehlgeschlagen: ' + res.data.message, 'error')
    }
  } catch (e) {
    showSnackbar?.('Generierung fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    generatingKey.value = false
  }
}

function copyPublicKey() {
  navigator.clipboard.writeText(generatedPublicKey.value)
  showSnackbar?.('Public Key kopiert', 'success')
}

async function saveNotifications() {
  saving.value = true
  try {
    await api.put('/api/notifications/settings', notifications.value)
    showSnackbar?.('Benachrichtigungs-Einstellungen gespeichert', 'success')
  } catch (e) {
    showSnackbar?.('Speichern fehlgeschlagen', 'error')
  } finally {
    saving.value = false
  }
}

async function testGotify() {
  testing.value = true
  try {
    // Erst speichern, dann testen
    await api.put('/api/notifications/settings', notifications.value)
    const res = await api.post('/api/notifications/settings/send-test-gotify')
    if (res.data.success) {
      showSnackbar?.('Gotify-Test erfolgreich', 'success')
    } else {
      showSnackbar?.('Test fehlgeschlagen: ' + res.data.message, 'error')
    }
  } catch (e) {
    showSnackbar?.('Test fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    testing.value = false
  }
}

async function testSmtp() {
  testingSmtp.value = true
  try {
    // Erst speichern, dann testen
    await api.put('/api/notifications/settings', notifications.value)
    const res = await api.post('/api/notifications/settings/send-test-email')
    if (res.data.success) {
      showSnackbar?.(res.data.message || 'Test-E-Mail gesendet', 'success')
    } else {
      showSnackbar?.('Test fehlgeschlagen: ' + res.data.message, 'error')
    }
  } catch (e) {
    showSnackbar?.('Test fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    testingSmtp.value = false
  }
}

async function createBackup() {
  backupLoading.value = true
  try {
    // POST statt GET verwenden!
    const response = await api.post('/api/backup/create')
    if (response.data.success) {
      showSnackbar?.('Backup erstellt: ' + response.data.filename, 'success')
      await loadBackups()
    } else {
      showSnackbar?.('Backup fehlgeschlagen: ' + response.data.message, 'error')
    }
  } catch (e) {
    showSnackbar?.('Backup fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    backupLoading.value = false
  }
}

async function downloadBackup(backupId) {
  try {
    const response = await api.get(`/api/backup/download/${backupId}`, {
      responseType: 'blob'
    })
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    const contentDisposition = response.headers['content-disposition']
    const filename = contentDisposition
      ? contentDisposition.split('filename=')[1]?.replace(/"/g, '')
      : `backup-${backupId}.zip`
    link.setAttribute('download', filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
  } catch (e) {
    showSnackbar?.('Download fehlgeschlagen', 'error')
  }
}

function openRestoreDialog() {
  restoreFile.value = null
  restoreDialog.value = true
}

async function restoreBackup() {
  if (!restoreFile.value) return

  restoring.value = true
  try {
    const formData = new FormData()
    formData.append('file', restoreFile.value)

    const response = await api.post('/api/backup/restore', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    if (response.data.success) {
      showSnackbar?.('Backup wiederhergestellt', 'success')
      restoreDialog.value = false
      // Seite neu laden um neue Daten anzuzeigen
      window.location.reload()
    } else {
      showSnackbar?.('Wiederherstellen fehlgeschlagen: ' + response.data.message, 'error')
    }
  } catch (e) {
    showSnackbar?.('Wiederherstellen fehlgeschlagen: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    restoring.value = false
  }
}

function formatBackupDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('de-DE')
}

function formatSize(bytes) {
  if (!bytes) return '-'
  const mb = bytes / (1024 * 1024)
  return mb.toFixed(1) + ' MB'
}

onMounted(async () => {
  await loadSettings()
  await loadSshKeys()
  await loadSecurityStatus()
  if (route.query.tab) {
    tab.value = route.query.tab
  }
})
</script>

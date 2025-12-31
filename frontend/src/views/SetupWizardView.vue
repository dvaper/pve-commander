<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" md="8" lg="6">
        <v-card class="elevation-12">
          <v-toolbar color="primary" dark flat>
            <v-icon class="mr-2">mdi-cog-outline</v-icon>
            <v-toolbar-title>PVE Commander - Setup</v-toolbar-title>
          </v-toolbar>

          <v-stepper v-model="step" :items="steps" flat>
            <!-- Schritt 1: Willkommen -->
            <template v-slot:item.1>
              <v-card flat>
                <v-card-text class="text-center py-8">
                  <v-icon size="80" color="primary" class="mb-4">
                    mdi-server-network
                  </v-icon>
                  <h2 class="text-h5 mb-4">Willkommen bei PVE Commander</h2>
                  <p class="text-body-1 text-grey-darken-1 mb-6">
                    Dieser Assistent hilft dir bei der Erstkonfiguration.
                    Du benötigst Zugriff auf deinen Proxmox VE Server mit einem API-Token.
                  </p>

                  <v-alert type="info" variant="tonal" class="text-left mb-4">
                    <div class="text-subtitle-2 mb-2">Voraussetzungen:</div>
                    <ul class="pl-4">
                      <li>Proxmox VE Server - unterstützte Formate:
                        <ul class="pl-2 text-body-2">
                          <li><code>192.168.1.100</code> - IP-Adresse (Port 8006 wird automatisch hinzugefügt)</li>
                          <li><code>proxmox.example.com</code> - Hostname (Port 8006 wird automatisch hinzugefügt)</li>
                          <li><code>https://proxmox.example.com</code> - Reverse Proxy (Standard HTTPS Port 443)</li>
                        </ul>
                      </li>
                      <li>API-Token mit entsprechenden Berechtigungen</li>
                      <li>Netzwerkzugriff auf den Proxmox-Server</li>
                    </ul>
                  </v-alert>

                  <v-alert type="warning" variant="tonal" class="text-left">
                    <div class="text-subtitle-2">Noch keinen API-Token?</div>
                    <p class="text-body-2 mb-0">
                      Kein Problem! Im nächsten Schritt findest du eine ausführliche Anleitung
                      zur Erstellung eines API-Tokens in Proxmox.
                    </p>
                  </v-alert>
                </v-card-text>
              </v-card>
            </template>

            <!-- Schritt 2: Proxmox Konfiguration -->
            <template v-slot:item.2>
              <v-card flat>
                <v-card-text>
                  <h3 class="text-h6 mb-4">
                    <v-icon class="mr-2">mdi-server</v-icon>
                    Proxmox Verbindung
                  </h3>

                  <!-- Hilfe-Bereich für Token-Erstellung -->
                  <v-expansion-panels class="mb-4">
                    <v-expansion-panel>
                      <v-expansion-panel-title>
                        <v-icon class="mr-2" size="small" color="info">mdi-help-circle</v-icon>
                        <span class="text-body-2">Anleitung: API-Token in Proxmox erstellen</span>
                      </v-expansion-panel-title>
                      <v-expansion-panel-text>
                        <div class="text-body-2">
                          <p class="font-weight-bold mb-2">Schritt 1: API-Benutzer anlegen (optional)</p>
                          <p class="mb-3">
                            Falls noch kein API-Benutzer existiert:<br>
                            <code>Datacenter</code> &rarr; <code>Permissions</code> &rarr; <code>Users</code> &rarr; <code>Add</code><br>
                            <ul class="pl-4">
                              <li>User name: <code>terraform</code> (oder beliebig)</li>
                              <li>Realm: <code>Proxmox VE authentication server</code> (pve)</li>
                              <li>Ergebnis: <code>terraform@pve</code></li>
                            </ul>
                          </p>

                          <p class="font-weight-bold mb-2">Schritt 2: API-Token erstellen</p>
                          <p class="mb-3">
                            <code>Datacenter</code> &rarr; <code>Permissions</code> &rarr; <code>API Tokens</code> &rarr; <code>Add</code><br>
                            <ul class="pl-4">
                              <li>User: <code>terraform@pve</code></li>
                              <li>Token ID: <code>terraform-token</code> (oder beliebig)</li>
                              <li><strong class="text-error">Privilege Separation: DEAKTIVIEREN!</strong></li>
                            </ul>
                          </p>

                          <v-alert type="warning" variant="tonal" density="compact" class="mb-3">
                            <strong>Wichtig:</strong> Das Token Secret wird nur einmal angezeigt!
                            Kopiere es sofort und speichere es sicher.
                          </v-alert>

                          <p class="font-weight-bold mb-2">Schritt 3: Berechtigungen vergeben</p>
                          <p class="mb-3">
                            <code>Datacenter</code> &rarr; <code>Permissions</code> &rarr; <code>Add</code> &rarr; <code>User Permission</code><br>
                            <ul class="pl-4">
                              <li>Path: <code>/</code> (Root für alle Rechte)</li>
                              <li>User: <code>terraform@pve</code></li>
                              <li>Role: <code>Administrator</code> (oder eingeschränkte Rolle)</li>
                            </ul>
                          </p>

                          <p class="font-weight-bold mb-2">Ergebnis:</p>
                          <ul class="pl-4">
                            <li><strong>Token ID:</strong> <code>terraform@pve!terraform-token</code></li>
                            <li><strong>Token Secret:</strong> <code>xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx</code></li>
                          </ul>
                        </div>
                      </v-expansion-panel-text>
                    </v-expansion-panel>
                  </v-expansion-panels>

                  <v-text-field
                    v-model="config.proxmox_host"
                    label="Proxmox Host"
                    placeholder="192.168.1.100 oder https://proxmox.example.com"
                    prepend-inner-icon="mdi-ip-network"
                    hint="Direkt: IP/Hostname (Port 8006 wird hinzugefügt) | Reverse Proxy: https://hostname"
                    persistent-hint
                    variant="outlined"
                    density="compact"
                    class="mb-4"
                    :error-messages="errors.proxmox_host"
                    @update:model-value="clearError('proxmox_host')"
                  ></v-text-field>

                  <v-text-field
                    v-model="config.proxmox_token_id"
                    label="API Token ID"
                    placeholder="terraform@pve!terraform-token"
                    prepend-inner-icon="mdi-identifier"
                    hint="Format: benutzer@realm!token-name (z.B. terraform@pve!terraform-token)"
                    persistent-hint
                    variant="outlined"
                    density="compact"
                    class="mb-4"
                    :error-messages="errors.proxmox_token_id"
                    @update:model-value="clearError('proxmox_token_id')"
                  ></v-text-field>

                  <v-text-field
                    v-model="config.proxmox_token_secret"
                    label="API Token Secret"
                    placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                    prepend-inner-icon="mdi-key"
                    :type="showSecret ? 'text' : 'password'"
                    :append-inner-icon="showSecret ? 'mdi-eye' : 'mdi-eye-off'"
                    @click:append-inner="showSecret = !showSecret"
                    hint="Das UUID-Secret wird beim Erstellen des Tokens einmalig angezeigt"
                    persistent-hint
                    variant="outlined"
                    density="compact"
                    class="mb-4"
                    :error-messages="errors.proxmox_token_secret"
                    @update:model-value="clearError('proxmox_token_secret')"
                  ></v-text-field>

                  <v-checkbox
                    v-model="config.proxmox_verify_ssl"
                    label="SSL-Zertifikat verifizieren"
                    hint="Deaktivieren bei selbstsignierten Zertifikaten oder Verbindungsproblemen"
                    persistent-hint
                    density="compact"
                    class="mb-4"
                  ></v-checkbox>

                  <!-- Verbindungstest - erscheint nur wenn alle Felder ausgefüllt -->
                  <template v-if="canTest">
                    <v-divider class="my-4"></v-divider>

                    <v-btn
                      color="secondary"
                      variant="outlined"
                      :loading="testing"
                      @click="testConnection"
                    >
                      <v-icon left class="mr-2">mdi-connection</v-icon>
                      Verbindung testen
                    </v-btn>
                  </template>

                  <v-alert
                    v-if="testResult"
                    :type="testResult.success ? 'success' : 'error'"
                    variant="tonal"
                    class="mt-4"
                  >
                    <div class="font-weight-bold">{{ testResult.message }}</div>
                    <div v-if="testResult.success && testResult.version" class="text-body-2 mt-1">
                      Proxmox VE {{ testResult.version }}
                      <span v-if="testResult.cluster_name">
                        | Cluster: {{ testResult.cluster_name }}
                      </span>
                      <span v-if="testResult.node_count">
                        | {{ testResult.node_count }} Node(s)
                      </span>
                    </div>
                    <div v-if="testResult.error" class="text-body-2 mt-1">
                      {{ testResult.error }}
                    </div>
                  </v-alert>
                </v-card-text>
              </v-card>
            </template>

            <!-- Schritt 3: Optionale Einstellungen -->
            <template v-slot:item.3>
              <v-card flat>
                <v-card-text>
                  <h3 class="text-h6 mb-4">
                    <v-icon class="mr-2">mdi-tune</v-icon>
                    Optionale Einstellungen
                  </h3>

                  <!-- Warnung wenn Admin-Passwort fehlt -->
                  <v-alert
                    v-if="!config.app_admin_password || config.app_admin_password.length < 6"
                    type="warning"
                    variant="tonal"
                    class="mb-4"
                  >
                    <strong>Pflichtfeld:</strong> Bitte lege ein Admin-Passwort fest (min. 6 Zeichen).
                  </v-alert>

                  <v-expansion-panels v-model="optionsPanels" variant="accordion" multiple>
                    <!-- SSH/Ansible -->
                    <v-expansion-panel value="ssh">
                      <v-expansion-panel-title>
                        <v-icon class="mr-2" size="small">mdi-ansible</v-icon>
                        Ansible / SSH
                        <v-chip v-if="sshKeyConfigured" color="success" size="x-small" class="ml-2">
                          OK
                        </v-chip>
                      </v-expansion-panel-title>
                      <v-expansion-panel-text>
                        <SSHKeyManager
                          ref="sshKeyManager"
                          :initial-user="config.ansible_remote_user"
                          api-prefix="/api/setup"
                          @update:user="handleSshUserChange"
                          @key-changed="handleSshKeyChanged"
                          @config-loaded="handleSshConfigLoaded"
                        />
                      </v-expansion-panel-text>
                    </v-expansion-panel>

                    <!-- App Admin -->
                    <v-expansion-panel value="admin">
                      <v-expansion-panel-title>
                        <v-icon class="mr-2" size="small" color="warning">mdi-account-key</v-icon>
                        <strong>App Administrator</strong>
                        <v-chip v-if="!config.app_admin_password || config.app_admin_password.length < 6" color="error" size="x-small" class="ml-2">
                          Pflicht
                        </v-chip>
                        <v-chip v-else color="success" size="x-small" class="ml-2">
                          OK
                        </v-chip>
                      </v-expansion-panel-title>
                      <v-expansion-panel-text>
                        <v-alert type="info" variant="tonal" density="compact" class="mb-4">
                          Lege hier die Zugangsdaten für den Administrator der App fest.
                          Diese Daten werden für den Login in PVE Commander verwendet.
                        </v-alert>

                        <v-text-field
                          v-model="config.app_admin_user"
                          label="Admin-Benutzername"
                          prepend-inner-icon="mdi-account"
                          hint="Standard: admin"
                          persistent-hint
                          variant="outlined"
                          density="compact"
                          class="mb-4"
                        ></v-text-field>

                        <v-text-field
                          v-model="config.app_admin_password"
                          label="Admin-Passwort"
                          prepend-inner-icon="mdi-lock"
                          :type="showAppAdminPassword ? 'text' : 'password'"
                          :append-inner-icon="showAppAdminPassword ? 'mdi-eye' : 'mdi-eye-off'"
                          @click:append-inner="showAppAdminPassword = !showAppAdminPassword"
                          hint="Mindestens 6 Zeichen"
                          persistent-hint
                          variant="outlined"
                          density="compact"
                          class="mb-4"
                          :rules="[v => !!v || 'Passwort erforderlich', v => (v && v.length >= 6) || 'Min. 6 Zeichen']"
                        ></v-text-field>

                        <v-text-field
                          v-model="config.app_admin_email"
                          label="Admin E-Mail"
                          prepend-inner-icon="mdi-email"
                          hint="Optional"
                          persistent-hint
                          variant="outlined"
                          density="compact"
                        ></v-text-field>
                      </v-expansion-panel-text>
                    </v-expansion-panel>

                    <!-- NetBox -->
                    <v-expansion-panel value="netbox">
                      <v-expansion-panel-title>
                        <v-icon class="mr-2" size="small">mdi-ip-network-outline</v-icon>
                        NetBox IPAM
                      </v-expansion-panel-title>
                      <v-expansion-panel-text>
                        <v-radio-group v-model="netboxMode" class="mb-4">
                          <v-radio value="integrated" label="Integriertes NetBox (im Container)"></v-radio>
                          <v-radio value="external" label="Externes NetBox (eigene Instanz)"></v-radio>
                          <v-radio value="none" label="NetBox nicht verwenden"></v-radio>
                        </v-radio-group>

                        <!-- Integriertes NetBox -->
                        <div v-if="netboxMode === 'integrated'">
                          <v-alert type="warning" variant="tonal" density="compact" class="mb-4">
                            <v-icon start size="small">mdi-clock-outline</v-icon>
                            <strong>Erstinstallation:</strong> NetBox wird nach dem Setup-Wizard gestartet.
                            Die Initialisierung dauert ca. 5-10 Minuten (Datenbank-Migrationen).
                          </v-alert>

                          <v-alert type="info" variant="tonal" density="compact" class="mb-4">
                            Konfiguriere hier die Admin-Zugangsdaten fuer NetBox.
                            <br><br>
                            <strong>Hinweis:</strong> Fuer eine komplette Neuinstallation (inkl. NetBox-Daten)
                            verwende: <code>docker compose down -v</code>
                          </v-alert>

                          <v-text-field
                            v-model="config.netbox_external_url"
                            label="NetBox Externe URL (fuer Browser)"
                            prepend-inner-icon="mdi-open-in-new"
                            placeholder="https://netbox.example.com oder http://192.168.1.100:8081"
                            hint="URL unter der NetBox im Browser erreichbar ist (fuer Links im UI)"
                            persistent-hint
                            variant="outlined"
                            density="compact"
                            class="mb-4"
                          ></v-text-field>

                          <v-text-field
                            v-model="config.netbox_admin_user"
                            label="Admin-Benutzername"
                            prepend-inner-icon="mdi-account"
                            hint="Standard: admin"
                            persistent-hint
                            variant="outlined"
                            density="compact"
                            class="mb-4"
                          ></v-text-field>

                          <v-text-field
                            v-model="config.netbox_admin_password"
                            label="Admin-Passwort"
                            prepend-inner-icon="mdi-lock"
                            :type="showNetboxPassword ? 'text' : 'password'"
                            :append-inner-icon="showNetboxPassword ? 'mdi-eye' : 'mdi-eye-off'"
                            @click:append-inner="showNetboxPassword = !showNetboxPassword"
                            hint="Mindestens 4 Zeichen"
                            persistent-hint
                            variant="outlined"
                            density="compact"
                            class="mb-4"
                            :rules="[v => !!v || 'Passwort erforderlich', v => (v && v.length >= 4) || 'Min. 4 Zeichen']"
                          ></v-text-field>

                          <v-text-field
                            v-model="config.netbox_admin_email"
                            label="Admin E-Mail"
                            prepend-inner-icon="mdi-email"
                            hint="Optional, aber empfohlen"
                            persistent-hint
                            variant="outlined"
                            density="compact"
                            class="mb-4"
                          ></v-text-field>

                          <v-divider class="my-4"></v-divider>

                          <!-- Token ist fest vorgegeben fuer integriertes NetBox -->
                          <v-alert type="success" variant="tonal" density="compact" class="mb-2">
                            <v-icon start size="small">mdi-check-circle</v-icon>
                            API-Token ist automatisch konfiguriert
                          </v-alert>
                          <div class="text-caption text-grey mb-2">
                            Token: <code>{{ config.netbox_token.substring(0, 8) }}...{{ config.netbox_token.substring(32) }}</code>
                          </div>
                        </div>

                        <!-- Externes NetBox -->
                        <div v-if="netboxMode === 'external'">
                          <v-alert type="warning" variant="tonal" density="compact" class="mb-4">
                            Bei Verwendung eines externen NetBox wird der integrierte Container nicht genutzt.
                            Die Backend-URL muss vom Server aus erreichbar sein.
                          </v-alert>

                          <v-text-field
                            v-model="config.netbox_url"
                            label="NetBox Backend-URL (fuer API)"
                            placeholder="https://netbox.example.com"
                            prepend-inner-icon="mdi-web"
                            hint="URL fuer Backend-Kommunikation (API-Zugriff)"
                            persistent-hint
                            variant="outlined"
                            density="compact"
                            class="mb-4"
                          ></v-text-field>

                          <v-text-field
                            v-model="config.netbox_external_url"
                            label="NetBox Externe URL (fuer Browser)"
                            prepend-inner-icon="mdi-open-in-new"
                            placeholder="https://netbox.example.com"
                            hint="URL unter der NetBox im Browser erreichbar ist (fuer Links im UI)"
                            persistent-hint
                            variant="outlined"
                            density="compact"
                            class="mb-4"
                          ></v-text-field>

                          <v-text-field
                            v-model="config.netbox_token"
                            label="NetBox API Token"
                            prepend-inner-icon="mdi-key-variant"
                            hint="API-Token mit Schreibrechten"
                            persistent-hint
                            variant="outlined"
                            density="compact"
                          ></v-text-field>
                        </div>

                        <!-- Kein NetBox -->
                        <div v-if="netboxMode === 'none'">
                          <v-alert type="info" variant="tonal" density="compact">
                            Ohne NetBox ist keine automatische IP-Adressverwaltung verfügbar.
                            Du kannst NetBox später in den Einstellungen konfigurieren.
                          </v-alert>
                        </div>
                      </v-expansion-panel-text>
                    </v-expansion-panel>

                    <!-- Cloud-Init -->
                    <v-expansion-panel value="cloudinit">
                      <v-expansion-panel-title>
                        <v-icon class="mr-2" size="small">mdi-cloud-upload</v-icon>
                        Cloud-Init Konfiguration
                      </v-expansion-panel-title>
                      <v-expansion-panel-text>
                        <v-alert type="info" variant="tonal" density="compact" class="mb-4">
                          Cloud-Init konfiguriert neue VMs automatisch mit SSH-Zugang und Grundeinstellungen.
                          Diese Werte werden als Defaults fuer alle neuen VMs verwendet.
                        </v-alert>

                        <v-text-field
                          v-model="config.cloud_init_admin_username"
                          label="Admin-Benutzername"
                          prepend-inner-icon="mdi-account"
                          hint="Benutzername der auf neuen VMs erstellt wird (Standard: ansible)"
                          persistent-hint
                          variant="outlined"
                          density="compact"
                          class="mb-4"
                        ></v-text-field>

                        <v-text-field
                          v-model="config.cloud_init_admin_gecos"
                          label="Admin GECOS (Vollstaendiger Name)"
                          prepend-inner-icon="mdi-card-account-details"
                          hint="Angezeigter Name des Benutzers (z.B. 'Homelab Admin')"
                          persistent-hint
                          variant="outlined"
                          density="compact"
                          class="mb-4"
                        ></v-text-field>

                        <v-textarea
                          v-model="config.cloud_init_ssh_keys_text"
                          label="SSH Authorized Keys"
                          prepend-inner-icon="mdi-key"
                          hint="Ein SSH Public Key pro Zeile (ssh-ed25519 oder ssh-rsa ...)"
                          persistent-hint
                          variant="outlined"
                          density="compact"
                          rows="3"
                          class="mb-4"
                          placeholder="ssh-ed25519 AAAA... user@host"
                        ></v-textarea>

                        <v-checkbox
                          v-model="config.cloud_init_phone_home_enabled"
                          label="Phone-Home Callback aktivieren"
                          hint="VMs melden sich nach der Erstellung beim Server"
                          persistent-hint
                          density="compact"
                          class="mb-4"
                        ></v-checkbox>

                        <v-divider class="my-4"></v-divider>

                        <div class="text-subtitle-2 mb-2">NAS Snippets (optional)</div>
                        <v-alert type="info" variant="tonal" density="compact" class="mb-4">
                          Falls Cloud-Init Snippets auf einem NAS gespeichert werden sollen,
                          gib hier den Pfad und die Proxmox Storage-Referenz an.
                        </v-alert>

                        <v-text-field
                          v-model="config.cloud_init_nas_snippets_path"
                          label="NAS Snippets Pfad"
                          prepend-inner-icon="mdi-folder-network"
                          placeholder="/mnt/pve/nas/snippets"
                          hint="Pfad zum Snippets-Verzeichnis auf dem Proxmox-Node"
                          persistent-hint
                          variant="outlined"
                          density="compact"
                          class="mb-4"
                        ></v-text-field>

                        <v-text-field
                          v-model="config.cloud_init_nas_snippets_ref"
                          label="Proxmox Storage-Referenz"
                          prepend-inner-icon="mdi-database"
                          placeholder="nas:snippets"
                          hint="Storage-Referenz fuer cicustom (z.B. nas:snippets)"
                          persistent-hint
                          variant="outlined"
                          density="compact"
                        ></v-text-field>
                      </v-expansion-panel-text>
                    </v-expansion-panel>
                  </v-expansion-panels>
                </v-card-text>
              </v-card>
            </template>

            <!-- Schritt 4: Zusammenfassung -->
            <template v-slot:item.4>
              <v-card flat>
                <v-card-text>
                  <h3 class="text-h6 mb-4">
                    <v-icon class="mr-2">mdi-check-circle-outline</v-icon>
                    Zusammenfassung
                  </h3>

                  <v-table density="compact">
                    <tbody>
                      <tr>
                        <td class="font-weight-bold">Proxmox Host</td>
                        <td>{{ config.proxmox_host }}</td>
                      </tr>
                      <tr>
                        <td class="font-weight-bold">Token ID</td>
                        <td>{{ config.proxmox_token_id }}</td>
                      </tr>
                      <tr>
                        <td class="font-weight-bold">SSL-Verifizierung</td>
                        <td>{{ config.proxmox_verify_ssl ? 'Aktiviert' : 'Deaktiviert' }}</td>
                      </tr>
                      <tr>
                        <td class="font-weight-bold">Ansible-User</td>
                        <td>{{ config.ansible_remote_user }}</td>
                      </tr>
                      <tr>
                        <td class="font-weight-bold">App Administrator</td>
                        <td>{{ config.app_admin_user }} / {{ config.app_admin_password ? '******' : '(kein Passwort)' }}</td>
                      </tr>
                      <tr>
                        <td class="font-weight-bold">NetBox</td>
                        <td>
                          <span v-if="netboxMode === 'integrated'">
                            Integriert{{ config.netbox_token ? ' (Token konfiguriert)' : '' }}
                          </span>
                          <span v-else-if="netboxMode === 'external'">
                            Extern: {{ config.netbox_url || 'URL fehlt' }}
                          </span>
                          <span v-else>Deaktiviert</span>
                        </td>
                      </tr>
                      <tr v-if="netboxMode === 'integrated'">
                        <td class="font-weight-bold">NetBox Admin</td>
                        <td>{{ config.netbox_admin_user }} / {{ config.netbox_admin_password ? '******' : '(kein Passwort)' }}</td>
                      </tr>
                    </tbody>
                  </v-table>

                  <v-alert type="info" variant="tonal" class="mt-4">
                    <v-icon>mdi-information</v-icon>
                    Die Konfiguration wird automatisch übernommen.
                    Ein Container-Neustart ist <strong>nicht</strong> erforderlich.
                  </v-alert>
                </v-card-text>
              </v-card>
            </template>

            <!-- Navigation Actions -->
            <template v-slot:actions>
              <v-card-actions class="pa-4">
                <v-btn
                  v-if="step > 1"
                  variant="text"
                  @click="step--"
                  :disabled="saving"
                >
                  <v-icon left>mdi-chevron-left</v-icon>
                  Zurück
                </v-btn>

                <v-spacer></v-spacer>

                <v-btn
                  v-if="step < 4"
                  color="primary"
                  :disabled="!canProceed"
                  @click="nextStep"
                >
                  Weiter
                  <v-icon right>mdi-chevron-right</v-icon>
                </v-btn>

                <v-btn
                  v-else
                  color="success"
                  :loading="saving"
                  :disabled="!canSave"
                  @click="saveConfig"
                >
                  <v-icon left class="mr-2">mdi-content-save</v-icon>
                  Konfiguration speichern
                </v-btn>
              </v-card-actions>
            </template>
          </v-stepper>
        </v-card>

        <!-- Weiterleitung zur Login-Seite -->
        <v-dialog v-model="redirectingToLogin" persistent max-width="400">
          <v-card>
            <v-card-text class="text-center py-8">
              <v-progress-circular
                indeterminate
                color="success"
                size="64"
                class="mb-4"
              ></v-progress-circular>
              <h3 class="text-h6 mb-2">Setup abgeschlossen!</h3>
              <p class="text-body-2 text-grey-darken-1 mb-4">
                Weiterleitung zur Anmeldung...
              </p>
              <v-alert type="info" variant="tonal" density="compact">
                <strong>Login:</strong> {{ config.app_admin_user }} / (dein Passwort)
              </v-alert>
            </v-card-text>
          </v-card>
        </v-dialog>

        <!-- NetBox Initialisierungs-Dialog -->
        <v-dialog v-model="showNetboxInitDialog" persistent max-width="500">
          <v-card>
            <v-card-title class="text-h5 bg-primary text-white">
              <v-icon class="mr-2">mdi-database-sync</v-icon>
              NetBox Initialisierung
            </v-card-title>
            <v-card-text class="pt-4 text-center">
              <v-progress-circular
                v-if="netboxInitStatus === 'starting'"
                indeterminate
                color="primary"
                size="80"
                width="6"
                class="mb-4"
              ></v-progress-circular>

              <v-icon
                v-else-if="netboxInitStatus === 'ready'"
                size="80"
                color="success"
                class="mb-4"
              >mdi-check-circle</v-icon>

              <v-icon
                v-else-if="netboxInitStatus === 'error' || netboxInitStatus === 'timeout'"
                size="80"
                color="error"
                class="mb-4"
              >mdi-alert-circle</v-icon>

              <h3 class="text-h6 mb-2">{{ netboxInitMessage }}</h3>

              <p v-if="netboxInitStatus === 'starting'" class="text-body-2 text-grey-darken-1 mb-2">
                NetBox fuehrt ca. 200 Datenbank-Migrationen durch.<br>
                Dies dauert bei Erstinstallation 5-10 Minuten.
              </p>

              <p v-if="netboxElapsedSeconds > 0" class="text-caption text-grey">
                Vergangene Zeit: {{ formatTime(netboxElapsedSeconds) }}
              </p>

              <v-alert
                v-if="netboxInitStatus === 'error' || netboxInitStatus === 'timeout'"
                type="warning"
                variant="tonal"
                class="mt-4 text-left"
              >
                <p class="mb-2">NetBox konnte nicht initialisiert werden.</p>
                <p class="text-body-2">
                  Du kannst trotzdem fortfahren. NetBox kann spaeter manuell gestartet werden mit:
                </p>
                <code class="d-block mt-2">docker compose --profile netbox up -d</code>
              </v-alert>
            </v-card-text>
            <v-card-actions v-if="netboxInitStatus !== 'starting'">
              <v-spacer></v-spacer>
              <v-btn
                :color="netboxInitStatus === 'ready' ? 'success' : 'primary'"
                @click="finishSetup"
              >
                {{ netboxInitStatus === 'ready' ? 'Zur Anmeldung' : 'Trotzdem fortfahren' }}
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>

        <!-- Erfolgs-Dialog (Fallback wenn Restart nötig) -->
        <v-dialog v-model="showSuccessDialog" persistent max-width="500">
          <v-card>
            <v-card-title class="text-h5 bg-success text-white">
              <v-icon class="mr-2">mdi-check-circle</v-icon>
              Setup abgeschlossen
            </v-card-title>
            <v-card-text class="pt-4">
              <p>Die Konfiguration wurde erfolgreich gespeichert.</p>
              <p class="font-weight-bold">
                Bitte starte die Container neu, damit die Einstellungen wirksam werden:
              </p>
              <v-code class="d-block pa-3 bg-grey-lighten-4">
                docker compose down && docker compose up -d
              </v-code>
              <p class="mt-4 text-grey-darken-1">
                Nach dem Neustart kannst du dich mit deinen Zugangsdaten anmelden:<br>
                <strong>Benutzername:</strong> {{ config.app_admin_user }}<br>
                <strong>Passwort:</strong> (dein gewähltes Passwort)
              </p>
            </v-card-text>
            <v-card-actions>
              <v-spacer></v-spacer>
              <v-btn color="primary" @click="refreshPage">
                Seite neu laden
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import axios from 'axios'
import SSHKeyManager from '@/components/SSHKeyManager.vue'

// Stepper State
const step = ref(1)
const steps = [
  { title: 'Willkommen', value: 1 },
  { title: 'Proxmox', value: 2 },
  { title: 'Optionen', value: 3 },
  { title: 'Fertig', value: 4 },
]

// Default NetBox API Token (muss mit docker-compose.yml SUPERUSER_API_TOKEN uebereinstimmen!)
const DEFAULT_NETBOX_TOKEN = '0123456789abcdef0123456789abcdef01234567'

// Config State
const config = ref({
  proxmox_host: '',
  proxmox_token_id: '',
  proxmox_token_secret: '',
  proxmox_verify_ssl: false,
  ansible_remote_user: 'ansible',
  default_ssh_user: 'ansible',
  netbox_token: DEFAULT_NETBOX_TOKEN,  // Default-Token verwenden!
  netbox_url: '',
  netbox_external_url: '',  // Externe URL fuer Browser-Links
  // App Admin Credentials
  app_admin_user: 'admin',
  app_admin_password: '',
  app_admin_email: 'admin@local',
  // NetBox Admin Credentials
  netbox_admin_user: 'admin',
  netbox_admin_password: '',
  netbox_admin_email: 'admin@example.com',
  // Cloud-Init Einstellungen
  cloud_init_admin_username: 'ansible',
  cloud_init_admin_gecos: 'Homelab Admin',
  cloud_init_ssh_keys_text: '',  // Textarea: Ein Key pro Zeile
  cloud_init_phone_home_enabled: true,
  cloud_init_nas_snippets_path: '',
  cloud_init_nas_snippets_ref: '',
})

// NetBox Mode: 'integrated', 'external', 'none'
const netboxMode = ref('integrated')

// Berechnet die Standard-NetBox-URL basierend auf aktueller Browser-Adresse
function calculateDefaultNetboxUrl() {
  // NetBox laeuft auf Port 8081 (konfiguriert in docker-compose.yml)
  const currentHost = window.location.hostname
  const protocol = window.location.protocol
  return `${protocol}//${currentHost}:8081`
}

// Watcher: NetBox External URL automatisch setzen bei 'integrated' Modus
watch(netboxMode, (newMode) => {
  if (newMode === 'integrated' && !config.value.netbox_external_url) {
    config.value.netbox_external_url = calculateDefaultNetboxUrl()
  }
})

// Bei Mount: Initiale NetBox URL setzen wenn integrated Modus
onMounted(() => {
  if (netboxMode.value === 'integrated' && !config.value.netbox_external_url) {
    config.value.netbox_external_url = calculateDefaultNetboxUrl()
  }
})

// Options Panels - App Admin standardmaessig offen
const optionsPanels = ref(['admin'])

// UI State
const showSecret = ref(false)
const showAppAdminPassword = ref(false)
const showNetboxPassword = ref(false)
const testing = ref(false)
const saving = ref(false)
const testResult = ref(null)
const showSuccessDialog = ref(false)
const redirectingToLogin = ref(false)

// NetBox Initialisierung State
const showNetboxInitDialog = ref(false)
const netboxInitStatus = ref('starting') // starting, ready, error, timeout
const netboxInitMessage = ref('NetBox wird gestartet...')
const netboxElapsedSeconds = ref(0)
let netboxElapsedTimer = null

// SSH Key Manager
const sshKeyManager = ref(null)
const sshKeyConfigured = ref(false)

function handleSshUserChange(newUser) {
  config.value.ansible_remote_user = newUser
  config.value.default_ssh_user = newUser
}

function handleSshKeyChanged(result) {
  sshKeyConfigured.value = true
}

function handleSshConfigLoaded(sshConfig) {
  sshKeyConfigured.value = sshConfig?.has_key || false
  if (sshConfig?.ssh_user && sshConfig.ssh_user !== 'ansible') {
    config.value.ansible_remote_user = sshConfig.ssh_user
    config.value.default_ssh_user = sshConfig.ssh_user
  }
}

// Validation Errors
const errors = ref({
  proxmox_host: '',
  proxmox_token_id: '',
  proxmox_token_secret: '',
})

// Computed
const canTest = computed(() => {
  return config.value.proxmox_host &&
         config.value.proxmox_token_id &&
         config.value.proxmox_token_secret
})

const canProceed = computed(() => {
  if (step.value === 2) {
    // Proxmox-Schritt: Verbindung muss erfolgreich getestet sein
    return testResult.value?.success === true
  }
  return true
})

const canSave = computed(() => {
  // Proxmox-Verbindung muss erfolgreich sein
  if (!testResult.value?.success) return false
  // App-Admin Passwort muss mindestens 6 Zeichen haben
  if (!config.value.app_admin_password || config.value.app_admin_password.length < 6) return false
  return true
})

// Methods
function clearError(field) {
  errors.value[field] = ''
}

function generateNetboxToken() {
  // Fuer integriertes NetBox: Default-Token verwenden (muss mit docker-compose.yml uebereinstimmen)
  // Fuer externes NetBox: Zufaelligen Token generieren
  if (netboxMode.value === 'integrated') {
    config.value.netbox_token = DEFAULT_NETBOX_TOKEN
  } else {
    // Externes NetBox: Zufaelligen Token generieren
    const array = new Uint8Array(20)
    crypto.getRandomValues(array)
    config.value.netbox_token = Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('')
  }
}

function validateProxmoxFields() {
  let valid = true

  if (!config.value.proxmox_host) {
    errors.value.proxmox_host = 'Proxmox Host ist erforderlich'
    valid = false
  }

  if (!config.value.proxmox_token_id) {
    errors.value.proxmox_token_id = 'Token ID ist erforderlich'
    valid = false
  } else if (!config.value.proxmox_token_id.includes('!')) {
    errors.value.proxmox_token_id = 'Token ID muss das Format user@realm!token-name haben'
    valid = false
  }

  if (!config.value.proxmox_token_secret) {
    errors.value.proxmox_token_secret = 'Token Secret ist erforderlich'
    valid = false
  }

  return valid
}

async function testConnection() {
  if (!validateProxmoxFields()) {
    return
  }

  testing.value = true
  testResult.value = null

  try {
    const response = await axios.post('/api/setup/validate/proxmox', {
      host: config.value.proxmox_host,
      token_id: config.value.proxmox_token_id,
      token_secret: config.value.proxmox_token_secret,
      verify_ssl: config.value.proxmox_verify_ssl,
    })

    testResult.value = response.data
  } catch (error) {
    testResult.value = {
      success: false,
      message: 'Verbindungstest fehlgeschlagen',
      error: error.response?.data?.detail || error.message,
    }
  } finally {
    testing.value = false
  }
}

function nextStep() {
  if (step.value === 2 && !validateProxmoxFields()) {
    return
  }
  step.value++
}

async function saveConfig() {
  saving.value = true

  // NetBox-Konfiguration basierend auf Modus
  let netboxToken = null
  let netboxUrl = null
  let netboxAdminUser = 'admin'
  let netboxAdminPassword = 'admin'
  let netboxAdminEmail = 'admin@example.com'

  if (netboxMode.value === 'integrated') {
    netboxToken = config.value.netbox_token || null
    netboxUrl = null  // Verwendet Standard: http://netbox:8080
    netboxAdminUser = config.value.netbox_admin_user || 'admin'
    netboxAdminPassword = config.value.netbox_admin_password || 'admin'
    netboxAdminEmail = config.value.netbox_admin_email || 'admin@example.com'
  } else if (netboxMode.value === 'external') {
    netboxToken = config.value.netbox_token || null
    netboxUrl = config.value.netbox_url || null
  }
  // Bei 'none': beide bleiben null

  // Cloud-Init SSH Keys: Textarea zu Array konvertieren
  const cloudInitSshKeys = config.value.cloud_init_ssh_keys_text
    ? config.value.cloud_init_ssh_keys_text
        .split('\n')
        .map(key => key.trim())
        .filter(key => key.startsWith('ssh-'))
    : []

  try {
    // force=true erlaubt das erneute Ausfuehren des Setups (fuer Tests)
    const response = await axios.post('/api/setup/save?force=true', {
      proxmox_host: config.value.proxmox_host,
      proxmox_token_id: config.value.proxmox_token_id,
      proxmox_token_secret: config.value.proxmox_token_secret,
      proxmox_verify_ssl: config.value.proxmox_verify_ssl,
      ansible_remote_user: config.value.ansible_remote_user,
      default_ssh_user: config.value.default_ssh_user,
      // App Admin Credentials
      app_admin_user: config.value.app_admin_user,
      app_admin_password: config.value.app_admin_password,
      app_admin_email: config.value.app_admin_email,
      // NetBox
      netbox_token: netboxToken,
      netbox_url: netboxUrl,
      netbox_external_url: config.value.netbox_external_url || null,
      netbox_admin_user: netboxAdminUser,
      netbox_admin_password: netboxAdminPassword,
      netbox_admin_email: netboxAdminEmail,
      // Cloud-Init
      cloud_init_admin_username: config.value.cloud_init_admin_username,
      cloud_init_admin_gecos: config.value.cloud_init_admin_gecos,
      cloud_init_ssh_keys: cloudInitSshKeys,
      cloud_init_phone_home_enabled: config.value.cloud_init_phone_home_enabled,
      cloud_init_nas_snippets_path: config.value.cloud_init_nas_snippets_path || null,
      cloud_init_nas_snippets_ref: config.value.cloud_init_nas_snippets_ref || null,
    })

    // Prüfen ob Konfiguration direkt geladen wurde (kein Restart nötig)
    if (response.data.restart_required === false) {
      // Pruefen ob integriertes NetBox gewaehlt wurde
      if (netboxMode.value === 'integrated') {
        // NetBox-Initialisierung starten
        await startNetboxInitialization()
      } else {
        // Direkt zur Login-Seite weiterleiten
        redirectingToLogin.value = true
        setTimeout(() => {
          window.location.href = '/login'
        }, 1500)
      }
    } else {
      // Fallback: Restart erforderlich - Dialog anzeigen
      showSuccessDialog.value = true
    }
  } catch (error) {
    testResult.value = {
      success: false,
      message: 'Speichern fehlgeschlagen',
      error: error.response?.data?.detail || error.message,
    }
  } finally {
    saving.value = false
  }
}

function refreshPage() {
  window.location.reload()
}

// Zeitformatierung
function formatTime(seconds) {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

// NetBox Initialisierung starten
async function startNetboxInitialization() {
  showNetboxInitDialog.value = true
  netboxInitStatus.value = 'starting'
  netboxInitMessage.value = 'NetBox wird gestartet...'
  netboxElapsedSeconds.value = 0

  // Timer starten
  netboxElapsedTimer = setInterval(() => {
    netboxElapsedSeconds.value++
  }, 1000)

  try {
    // API aufrufen (wait_for_ready: false, damit wir selbst pollen koennen)
    const response = await axios.post('/api/setup/netbox/start', {
      wait_for_ready: false
    })

    if (!response.data.success) {
      clearInterval(netboxElapsedTimer)
      netboxInitStatus.value = 'error'
      netboxInitMessage.value = 'Fehler beim Starten'
      return
    }

    // Polling starten - pruefe Status alle 5 Sekunden
    netboxInitMessage.value = 'Datenbank-Migrationen laufen...'

    const maxWaitMs = 10 * 60 * 1000 // 10 Minuten
    const pollInterval = 5000 // 5 Sekunden
    const startTime = Date.now()

    const pollNetboxStatus = async () => {
      try {
        const statusResponse = await axios.get('/api/setup/netbox/status')

        if (statusResponse.data.ready) {
          // NetBox ist bereit!
          clearInterval(netboxElapsedTimer)
          netboxInitStatus.value = 'ready'
          netboxInitMessage.value = 'NetBox ist bereit!'

          // NetBox-Superuser synchronisieren
          try {
            await syncNetboxSuperuser()
          } catch (e) {
            console.warn('NetBox-Superuser Sync fehlgeschlagen:', e)
          }
          return
        }

        // Pruefen ob Timeout erreicht
        if (Date.now() - startTime > maxWaitMs) {
          clearInterval(netboxElapsedTimer)
          netboxInitStatus.value = 'timeout'
          netboxInitMessage.value = 'Timeout nach 10 Minuten'
          return
        }

        // Weiter pollen
        setTimeout(pollNetboxStatus, pollInterval)
      } catch (e) {
        // Bei Netzwerkfehler weiterpollen
        if (Date.now() - startTime > maxWaitMs) {
          clearInterval(netboxElapsedTimer)
          netboxInitStatus.value = 'timeout'
          netboxInitMessage.value = 'Timeout nach 10 Minuten'
          return
        }
        setTimeout(pollNetboxStatus, pollInterval)
      }
    }

    // Polling starten
    setTimeout(pollNetboxStatus, pollInterval)

  } catch (error) {
    clearInterval(netboxElapsedTimer)
    netboxInitStatus.value = 'error'
    netboxInitMessage.value = error.response?.data?.message || 'Fehler beim Starten von NetBox'
  }
}

// NetBox-Superuser synchronisieren (via save endpoint erneut aufrufen wuerde doppelten User erzeugen)
async function syncNetboxSuperuser() {
  // Der Superuser wird bereits als Background-Task im save-Endpoint erstellt
  // Hier koennen wir optional nochmal pruefen/warten
  console.log('NetBox ist bereit, Superuser wurde bereits synchronisiert')
}

// Setup abschliessen
function finishSetup() {
  showNetboxInitDialog.value = false
  if (netboxElapsedTimer) {
    clearInterval(netboxElapsedTimer)
  }
  redirectingToLogin.value = true
  setTimeout(() => {
    window.location.href = '/login'
  }, 1000)
}
</script>

<style scoped>
.v-stepper {
  box-shadow: none;
}
</style>

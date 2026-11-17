import { Download, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { api } from '../api'
import { createTransferBundle, mergeTransferBundle, transferModules, type TransferModule } from '../transfer'
import { nativeBridge } from '../native'
import { Button, Field, GlassPanel, Input } from './ui'
import { useToast } from './feedback'

export function DataTransferPanel() {
  const { t } = useTranslation()
  const { notify } = useToast()
  const fileRef = useRef<HTMLInputElement | null>(null)
  const [password, setPassword] = useState('')
  const [includeCredentials, setIncludeCredentials] = useState(true)
  const [modules, setModules] = useState<TransferModule[]>(transferModules)

  function toggleModule(module: TransferModule) {
    setModules((current) =>
      current.includes(module)
        ? current.filter((item) => item !== module)
        : [...current, module]
    )
  }

  async function exportData() {
    const bridge = nativeBridge()
    if (!bridge) {
      try {
        const blob = await api.exportTransfer({
          modules,
          include_credentials: includeCredentials,
          password,
        })
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = 'CrazyGame.crazygame'
        link.click()
        URL.revokeObjectURL(url)
        notify(t('settings.exported'), 'success')
      } catch {
        notify(t('settings.exportFailed'), 'error')
      }
      return
    }
    try {
      const bundle = createTransferBundle(
        bridge.readState(),
        modules,
        includeCredentials
      )
      const result = JSON.parse(bridge.exportState(bundle, password)) as {
        ok?: boolean
        error?: string
      }
      if (!result.ok) throw new Error(result.error || 'export_failed')
      notify(t('settings.exported'), 'success')
    } catch (reason) {
      notify(
        reason instanceof Error && reason.message === 'password_too_short'
          ? t('settings.passwordTooShort')
          : t('settings.exportFailed'),
        'error'
      )
    }
  }

  async function importData(file: File) {
    const bridge = nativeBridge()
    try {
      if (!bridge) {
        await api.importTransfer(file, password, modules)
        notify(t('settings.imported'), 'success')
        window.setTimeout(() => window.location.reload(), 350)
        return
      }
      const content = await file.text()
      const result = JSON.parse(bridge.importState(content, password)) as {
        ok?: boolean
        state?: string
        error?: string
      }
      if (!result.ok || !result.state) throw new Error(result.error || 'import_failed')
      bridge.writeState(mergeTransferBundle(bridge.readState(), result.state, modules))
      notify(t('settings.imported'), 'success')
      window.setTimeout(() => window.location.reload(), 350)
    } catch {
      notify(t('settings.importFailed'), 'error')
    }
  }

  return (
    <GlassPanel className="settings-card settings-wide reveal">
      <div className="section-head">
        <div>
          <p className="eyebrow">{t('settings.transfer')}</p>
          <h2>{t('settings.transferTitle')}</h2>
          <p className="muted-copy">{t('settings.transferHint')}</p>
        </div>
      </div>
      <div className="transfer-module-grid">
        {transferModules.map((module) => (
          <label key={module} className="check-row">
            <input
              type="checkbox"
              checked={modules.includes(module)}
              onChange={() => toggleModule(module)}
            />
            {t(`settings.transferModules.${module}`)}
          </label>
        ))}
      </div>
      <div className="check-grid">
        <label className="check-row">
          <input
            type="checkbox"
            checked={includeCredentials}
            onChange={(event) => setIncludeCredentials(event.target.checked)}
          />
          {t('settings.includeCredentials')}
        </label>
      </div>
      <Field label={t('settings.transferPassword')} hint={t('settings.transferPasswordHint')}>
        <Input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          minLength={8}
        />
      </Field>
      <div className="transfer-actions">
        <Button
          className="full-button"
          onClick={() => void exportData()}
          disabled={!modules.length || password.length < 8}
        >
          <Download size={16} />
          {t('settings.exportData')}
        </Button>
        <Button
          variant="secondary"
          className="full-button"
          onClick={() => fileRef.current?.click()}
          disabled={!modules.length || password.length < 8}
        >
          <Upload size={16} />
          {t('settings.importData')}
        </Button>
      </div>
      <input
        ref={fileRef}
        hidden
        type="file"
        accept=".crazygame,application/octet-stream,text/plain"
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (file) void importData(file)
          event.target.value = ''
        }}
      />
    </GlassPanel>
  )
}

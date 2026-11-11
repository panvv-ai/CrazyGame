import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'

import { api } from '../api'
import { LineChart } from '../components/LineChart'
import {
  Badge,
  Button,
  EmptyState,
  Field,
  GlassPanel,
  Input,
  InstrumentMark,
  Loading,
  Metric,
  Modal,
  PageHeader,
} from '../components/ui'
import {
  changeClass,
  chartRangeDays,
  formatPercent,
  instrumentScope,
  type ChartRange,
  type InstrumentScope,
} from '../lib'
import { defaultScope, kindForScope, scopesForKind } from '../scopes'
import type {
  AssetGroup,
  GroupMemberPoint,
  GroupPoint,
  WatchlistItem,
  WatchlistKind,
} from '../types'

interface DraftMember {
  instrument_id: number
  weight: number
}

export function GroupsPage() {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const [kind, setKind] = useState<WatchlistKind>('stock')
  const [scope, setScope] = useState<InstrumentScope>('stock_cn')
  const [groups, setGroups] = useState<AssetGroup[]>([])
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [series, setSeries] = useState<GroupPoint[]>([])
  const [memberSeries, setMemberSeries] = useState<GroupMemberPoint[]>([])
  const [range, setRange] = useState<ChartRange>('1y')
  const [loading, setLoading] = useState(true)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<AssetGroup | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [draftMembers, setDraftMembers] = useState<DraftMember[]>([])
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    try {
      const [groupPayload, stockPayload, fundPayload] = await Promise.all([
        api.groups(),
        api.watchlist('stock'),
        api.watchlist('fund'),
      ])
      const summaries = await Promise.all(
        groupPayload.items.map((group) => api.groupSummary(group.id))
      )
      const supportedGroups = summaries.filter((group) => group.scope !== 'mixed')
      setGroups(supportedGroups)
      setWatchlist([...stockPayload.items, ...fundPayload.items])
      const requested = Number(searchParams.get('id') || 0)
      const scopedGroups = supportedGroups.filter((group) => group.scope === scope)
      const nextId =
        scopedGroups.find((group) => group.id === requested)?.id ??
        scopedGroups.find((group) => group.id === selectedId)?.id ??
        scopedGroups[0]?.id ??
        null
      setSelectedId(nextId)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  useEffect(() => {
    if (!selectedId) {
      setSeries([])
      return
    }
    api
      .groupSeries(selectedId, chartRangeDays(range))
      .then((payload) => {
        setSeries(payload.points)
        setMemberSeries(payload.members)
      })
      .catch(() => {
        setSeries([])
        setMemberSeries([])
      })
  }, [selectedId, range])

  const selected = groups.find((group) => group.id === selectedId) ?? null
  const visibleGroups = groups.filter((group) => group.scope === scope)
  const thirtyDayChange = useMemo(() => {
    if (series.length < 2) return null
    const latest = series[series.length - 1]
    const cutoff = new Date(`${latest.date}T00:00:00Z`)
    cutoff.setUTCDate(cutoff.getUTCDate() - 30)
    const first = series.find(
      (point) => new Date(`${point.date}T00:00:00Z`) >= cutoff
    )
    if (!first || first.value <= 0) return null
    return (latest.value / first.value - 1) * 100
  }, [series])
  const uniqueWatchlist = useMemo(() => {
    const seen = new Set<number>()
    return watchlist.filter((item) => {
      if (seen.has(item.instrument_id)) return false
      seen.add(item.instrument_id)
      return true
    })
  }, [watchlist])
  const visibleWatchlist = uniqueWatchlist.filter(
    (item) => instrumentScope(item) === scope
  )

  useEffect(() => {
    const scopedGroups = groups.filter((group) => group.scope === scope)
    if (scopedGroups.some((group) => group.id === selectedId)) return
    const requested = Number(searchParams.get('id') || 0)
    const nextId =
      scopedGroups.find((group) => group.id === requested)?.id ??
      scopedGroups[0]?.id ??
      null
    setSelectedId(nextId)
    setSearchParams(nextId ? { id: String(nextId) } : {}, { replace: true })
  }, [groups, scope])

  function switchScope(next: InstrumentScope) {
    setKind(kindForScope(next))
    setScope(next)
  }

  function switchKind(next: WatchlistKind) {
    switchScope(defaultScope(next))
  }

  const scopeOptions = scopesForKind(kind)

  function openCreate() {
    setEditing(null)
    setName('')
    setDescription('')
    setDraftMembers([])
    setModalOpen(true)
  }

  function openEdit(group: AssetGroup) {
    setEditing(group)
    setName(group.name)
    setDescription(group.description)
    setDraftMembers(
      group.members.map((member) => ({
        instrument_id: member.instrument_id,
        weight: Math.round(member.normalized_weight * 100),
      }))
    )
    setModalOpen(true)
  }

  async function saveGroup() {
    if (!name.trim() || draftMembers.length === 0) {
      setError(t('groups.noMembers'))
      return
    }
    try {
      const payload = {
        name: name.trim(),
        description,
        members: draftMembers.filter((member) => member.weight > 0),
      }
      const saved = editing
        ? await api.updateGroup(editing.id, payload)
        : await api.createGroup(payload)
      setModalOpen(false)
      setSearchParams({ id: String(saved.id) })
      await load()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('common.unknownError'))
    }
  }

  async function remove(group: AssetGroup) {
    if (!window.confirm(t('groups.deleteConfirm'))) return
    await api.removeGroup(group.id)
    await load()
  }

  function toggleMember(instrumentId: number) {
    setDraftMembers((current) =>
      current.some((member) => member.instrument_id === instrumentId)
        ? current.filter((member) => member.instrument_id !== instrumentId)
        : [...current, { instrument_id: instrumentId, weight: 10 }]
    )
  }

  const totalWeight = draftMembers.reduce((sum, member) => sum + member.weight, 0)

  return (
    <>
      <PageHeader
        eyebrow={t('groups.eyebrow')}
        title={t('groups.title')}
        subtitle={t('groups.subtitle')}
        action={
          <Button onClick={openCreate}>
            <Plus size={16} />
            {t('groups.newGroup')}
          </Button>
        }
      />
      <div className="scope-switcher reveal">
        <div className="segmented-control">
          <button className={kind === 'stock' ? 'active' : ''} onClick={() => switchKind('stock')}>
            {t('watchlist.stocks')}
          </button>
          <button className={kind === 'fund' ? 'active' : ''} onClick={() => switchKind('fund')}>
            {t('watchlist.funds')}
          </button>
        </div>
        <div className="segmented-control scope-control">
          {scopeOptions.map((option) => (
            <button
              key={option.scope}
              className={scope === option.scope ? 'active' : ''}
              onClick={() => switchScope(option.scope)}
            >
              {t(option.label)}
            </button>
          ))}
        </div>
      </div>
      {error ? <p className="form-error">{error}</p> : null}
      {loading ? (
        <Loading />
      ) : visibleGroups.length ? (
        <div className="groups-workspace">
          <aside className="group-list">
            {visibleGroups.map((group) => (
              <button
                key={group.id}
                className={`group-list-item ${group.id === selectedId ? 'active' : ''}`}
                onClick={() => {
                  setSelectedId(group.id)
                  setSearchParams({ id: String(group.id) })
                }}
              >
                <span>
                  <strong>{group.name}</strong>
                  <small>{group.members.length} {t('groups.members')}</small>
                </span>
                <span className={changeClass(group.day_change_pct)}>
                  {formatPercent(group.day_change_pct)}
                </span>
              </button>
            ))}
          </aside>

          {selected ? (
            <div className="group-detail">
              <GlassPanel className="group-hero">
                <div className="section-head">
                  <div>
                    <p className="eyebrow">{t('groups.dayChange')}</p>
                    <h2>{selected.name}</h2>
                    <p className="muted-copy">{selected.description}</p>
                  </div>
                  <div className="inline-actions">
                    <button className="icon-button" onClick={() => openEdit(selected)} aria-label={t('common.edit')}>
                      <Pencil size={16} />
                    </button>
                    <button className="icon-button danger" onClick={() => remove(selected)} aria-label={t('common.delete')}>
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
                <div className="metric-row">
                  <Metric
                    label={t('groups.dayChange')}
                    value={formatPercent(selected.day_change_pct)}
                    tone={changeClass(selected.day_change_pct)}
                  />
                  <Metric
                    label={t('groups.coverage')}
                    value={`${Math.round((selected.coverage ?? 0) * 100)}%`}
                  />
                  <Metric
                    label={t('groups.thirtyDay')}
                    value={formatPercent(thirtyDayChange)}
                    tone={changeClass(thirtyDayChange)}
                  />
                  <Metric label={t('groups.members')} value={selected.members.length} />
                </div>
              </GlassPanel>

              <GlassPanel className="chart-panel">
                <div className="section-head">
                  <div>
                    <p className="eyebrow">NORMALIZED · 100</p>
                    <h2>{t('groups.curve')}</h2>
                  </div>
                  <div className="range-switch">
                    {(['1m', '3m', '1y', '3y', 'all'] as ChartRange[]).map((item) => (
                      <button
                        key={item}
                        className={range === item ? 'active' : ''}
                        onClick={() => setRange(item)}
                      >
                        {t(
                          item === '1m'
                            ? 'groups.range1m'
                            : item === '3m'
                              ? 'groups.range3m'
                              : item === '1y'
                                ? 'groups.range1y'
                                : item === '3y'
                                  ? 'groups.range3y'
                                  : 'groups.rangeAll'
                        )}
                      </button>
                    ))}
                  </div>
                </div>
                {series.length > 1 ? (
                  <LineChart
                    height={320}
                    series={[
                      {
                        id: `group-${selected.id}`,
                        label: `${selected.name} · aggregate`,
                        color: '#a8b8ff',
                        points: series,
                      },
                      ...memberSeries.slice(0, 5).map((member, index) => ({
                        id: `member-${member.instrument_id}`,
                        label: member.name,
                        color: ['#81d8e8', '#a78bfa', '#50d7a2', '#f7c873', '#ff8793'][index],
                        points: member.points,
                      })),
                    ]}
                  />
                ) : (
                  <div className="chart-placeholder">{t('common.noData')}</div>
                )}
              </GlassPanel>

              <GlassPanel>
                <div className="section-head">
                  <h2>{t('groups.members')}</h2>
                  <Badge>{selected.members.length}</Badge>
                </div>
                <div className="member-table">
                  {selected.members.map((member) => (
                    <div className="member-row" key={member.instrument_id}>
                      <div className="instrument-identity">
                        <InstrumentMark
                          name={member.name}
                          symbol={member.symbol}
                          market={member.market}
                        />
                        <span>
                          <strong>{member.name}</strong>
                          <small>{member.symbol} · {t(`market.${member.market}`)}</small>
                        </span>
                      </div>
                      <span className="weight-track">
                        <span style={{ width: `${member.normalized_weight * 100}%` }} />
                      </span>
                      <strong>{Math.round(member.normalized_weight * 100)}%</strong>
                    </div>
                  ))}
                </div>
              </GlassPanel>
            </div>
          ) : null}
        </div>
      ) : (
        <GlassPanel>
          <EmptyState
            title={t('groups.empty')}
            action={<Button onClick={openCreate}>{t('groups.newGroup')}</Button>}
          />
        </GlassPanel>
      )}

      <Modal
        open={modalOpen}
        title={t(editing ? 'groups.editGroup' : 'groups.newGroup')}
        onClose={() => setModalOpen(false)}
      >
        <div className="form-grid">
          <Field label={t('groups.name')}>
            <Input value={name} onChange={(event) => setName(event.target.value)} />
          </Field>
          <Field label={t('groups.description')}>
            <Input value={description} onChange={(event) => setDescription(event.target.value)} />
          </Field>
        </div>
        <div className="member-picker">
          <div className="section-head">
            <h3>{t('groups.members')}</h3>
            <span className="muted-copy">
              {totalWeight > 0 ? `${totalWeight}%` : t('groups.weight')}
            </span>
          </div>
          {visibleWatchlist.length ? (
            visibleWatchlist.map((item) => {
              const draft = draftMembers.find(
                (member) => member.instrument_id === item.instrument_id
              )
              return (
                <div className={`member-pick-row ${draft ? 'selected' : ''}`} key={item.instrument_id}>
                  <button className="member-check" onClick={() => toggleMember(item.instrument_id)}>
                    <span>{draft ? '✓' : '+'}</span>
                    <span>
                      <strong>{item.name}</strong>
                      <small>{item.symbol} · {t(`asset.${item.asset_type}`)}</small>
                    </span>
                  </button>
                  {draft ? (
                    <Input
                      type="number"
                      min="0.1"
                      step="1"
                      value={draft.weight}
                      onChange={(event) =>
                        setDraftMembers((current) =>
                          current.map((member) =>
                            member.instrument_id === item.instrument_id
                              ? { ...member, weight: Number(event.target.value) }
                              : member
                          )
                        )
                      }
                    />
                  ) : null}
                </div>
              )
            })
          ) : (
            <p className="muted-copy">{t('groups.noScopeMembers')}</p>
          )}
        </div>
        <div className="modal-actions">
          <Button variant="ghost" onClick={() => setModalOpen(false)}>
            {t('common.cancel')}
          </Button>
          <Button onClick={saveGroup}>{t('common.save')}</Button>
        </div>
      </Modal>
    </>
  )
}


import { readJourney } from '../journey'
import type { TagLevel, TagNode, TagsBlock } from '../tu/types'
import { preloadPhotos } from '../ui/common'

// The tag -> subtag -> place tree one tags block opens (docs/TRIP_UNDERSTANDING.md §19). The root comes with the block;
// every deeper level is one read-only request (Engine.tag_stage), fetched as soon as its card is in front and kept.

export const ROOT = ''

export function rootLevel(block: TagsBlock): TagLevel {
  const tags = block.level === 'tags'
  const nodes: TagNode[] = block.subtags.map(s => ({ ref: s.id, kind: tags ? 'tag' : 'subtag', label: s.label, count: s.count, cover: s.cover[0] ?? null, has_children: true }))
  if (block.all.length) nodes.push({ ref: '*', kind: 'all', label: 'Xem tất cả', count: block.all.length, cover: block.all_cover ?? null, has_children: true })
  const label = block.title ?? (tags ? 'Bạn muốn khám phá điều gì?' : `${block.total} nơi hợp ý bạn`) // the assistant's own short question when it wrote one
  return { sig: block.sig ?? '', ref: ROOT, label, count: block.total, wished: false, nodes }
}

export const photoOf = (n: TagNode) => n.card?.photos[0] ?? n.cover

export class Tree {
  private done = new Map<string, TagLevel>()
  private pending = new Map<string, Promise<TagLevel>>()
  constructor(readonly sid: string | null, readonly block: TagsBlock) { this.done.set(ROOT, rootLevel(block)) }

  get(ref: string): TagLevel | undefined { return this.done.get(ref) }

  load(ref: string): Promise<TagLevel> {
    const got = this.done.get(ref)
    if (got) return Promise.resolve(got)
    const wait = this.pending.get(ref)
    if (wait) return wait
    if (!this.sid || !this.block.sig) return Promise.reject(new Error('no trip'))
    const q = `block=${encodeURIComponent(this.block.sig)}&path=${encodeURIComponent(ref)}`
    const p = readJourney<TagLevel>(this.sid, `trip/stage?${q}`).then(level => {
      this.done.set(ref, level)
      preloadPhotos(level.nodes.slice(0, 7).map(photoOf)) // the cards that fan out first are in the cache before the user taps
      return level
    }).finally(() => this.pending.delete(ref))
    this.pending.set(ref, p)
    return p
  }
}

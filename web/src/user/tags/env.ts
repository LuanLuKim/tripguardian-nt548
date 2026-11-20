import { createContext, useContext } from 'react'

// What the tag stage needs from the chat screen: the trip it reads for, the two writes it can make (both without a model
// call) and the turn Xong sends, all queued by the screen so a quick run of picks is never dropped. Understand.tsx provides it.
export interface TagEnv {
  sid: string | null
  like: (id: string, on: boolean) => void // a place of the stage becomes (or stops being) a want
  wish: (sig: string, path: string, on: boolean) => void // a whole kind becomes (or stops being) a soft preference
  explore: (sig: string, chips: string[], shown: string) => void // Xong with picks: the assistant reads them and opens a new direction (one model call)
}

export const TagEnvContext = createContext<TagEnv>({ sid: null, like: () => {}, wish: () => {}, explore: () => {} })
export const useTagEnv = () => useContext(TagEnvContext)

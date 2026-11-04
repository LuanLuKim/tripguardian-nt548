import { createContext, useContext } from 'react'

// What the tag stage needs from the chat screen: the trip it reads for, and the two writes it can make (both without a
// model call, both queued by the screen so a quick run of picks is never dropped). Understand.tsx provides it.
export interface TagEnv {
  sid: string | null
  like: (id: string, on: boolean) => void // a place of the stage becomes (or stops being) a want
  wish: (sig: string, path: string, on: boolean) => void // a whole kind becomes (or stops being) a soft preference
}

export const TagEnvContext = createContext<TagEnv>({ sid: null, like: () => {}, wish: () => {} })
export const useTagEnv = () => useContext(TagEnvContext)

import { info } from '../lib'
import { PlaceSheet } from '../ui/PlaceSheet'
import { SelectedBar } from '../ui/SelectedBar'
import { Page, useTitle } from '../ui/Shell'
import { useEditTicket } from './Explore'

// The shared link of a place (/explore/place/:id): the "Xem chi tiết" sheet as a page.
export function PlaceDetail({ id }: { id: string }) {
  useTitle(info(id)?.name ?? 'Địa điểm')
  const editTicket = useEditTicket()
  return (
    <>
      <Page className="tg-ps is-page"><PlaceSheet id={id} /></Page>
      <SelectedBar onRelax={editTicket} />
    </>
  )
}

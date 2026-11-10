// Snapshot comparisons omit only the metadata extracted in Run 17, never geometry.
export function legacyObject(object) {
  const {sign,cutaway,interior,...legacy}=object;
  return legacy;
}
export function legacyHotspot(spot) {
  const {cutaway,fill,building,pinOffset,...legacy}=spot;
  return legacy;
}
export function legacyPlace(data) {
  const result=structuredClone(data);
  for(const key of ['tourTitle','tourCaption','location','kits','routeSharpBounds'])delete result[key];
  delete result.site.landscape;delete result.site.hill?.undulationEndZ;
  result.objects=result.objects.map(legacyObject);
  result.hotspots=result.hotspots.map(legacyHotspot);
  return result;
}

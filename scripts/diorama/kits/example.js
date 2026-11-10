// Test fixture only; not listed by any shipped place.
registerObjectType('example_box', object => {
  mesh(new THREE.BoxGeometry(...object.size), object.color || palette.ochre,
    ...object.position).name = 'example-kit-box';
});

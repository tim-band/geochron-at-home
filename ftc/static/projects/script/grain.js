function forEach(arr, f) {
    for (var i = 0; i !== arr.length; ++i) {
        f(arr[i], i);
    }
}

function forEachInCycle(arr, f) {
    var lastI = arr.length - 1;
    var lastV = arr[lastI];
    forEach(arr, function(v, i) {
        f(lastV, v, lastI, i);
        lastV = v;
        lastI = i;
    });
}

function pointsClose(a, b, closeness) {
    return Math.max(Math.abs(a.x - b.x), Math.abs(a.y - b.y)) < closeness;
}

// returns the point on the (extended) line start-end closest to the
// point pt, provided that it is less than closeness away from the
// extended line.
function closePointOnLine(pt, start, end, closeness) {
    // vector of line
    var vx = end.y - start.y;
    var vy = end.x - start.x;
    // pt relative to start of line
    var px = pt.y - start.y;
    var py = pt.x - start.x;
    // p dot v
    var pv = px * vx + py * vy;
    // |v| squared
    var v2 = vx * vx + vy * vy;
    // closest point is how far along v?
    var prop = pv / v2;
    // which is which point?
    var i = {
        x: start.x + prop * vx,
        y: start.y + prop * vy
    };
    if (pointsClose(i, pt, closeness)) {
        return i;
    }
    return null;
}

function linesCross(aStart, aEnd, bStart, bEnd) {
    var ad = [aEnd[0] - aStart[0], aEnd[1] - aStart[1]];
    var bd = [bEnd[0] - bStart[0], bEnd[1] - bStart[1]];
    var max = ad[1] * bd[0] + bd[1] * ad[0];
    var min = 0;
    if (max < 0) {
        min = max;
        max = 0;
    }
    for (var i = 0; i !== 2; ++i) {
        var a = ad[1-i] * (aStart[i] - bStart[i]) - ad[i] * (aStart[1-i] - bStart[1-i]);
        if (a < min || max < a) {
            return false;
        }
    }
    return true;
}

function noop() { }

function makeMap(image_height, image_width, image_urls, region_points) {
    var yox = image_height / image_width;
    var mapView = [yox / 2.0, 0.5];
    var mapZoom = 11;
    var imageBounds = [
        [0.0, 0.0],
        [yox, 1.0]
    ];
    var imageOverlays = image_urls.map(function(url) {
        return L.imageOverlay(url, imageBounds, { zIndex: 1 });
    });
    var map = L.map('map', {
        center: mapView,
        zoom: mapZoom,
        minZoom: mapZoom - 2,
        maxZoom: mapZoom + 3,
        scrollWheelZoom: false,
        //doubleClickZoom: false
        /* zoomControl: false */
        layers: imageOverlays,
        attributionControl: false,
    });
    var region_layer = L.polygon(region_points, {
        color: 'white',
        fill: false,
        bubblingMouseEvents: false,
    }).addTo(map);
    currentFront = imageOverlays.length - 1;
    function bringToFront(layerNumber) {
        if (0 <= layerNumber && layerNumber < imageOverlays.length) {
            imageOverlays[currentFront].setZIndex(1);
            currentFront = layerNumber;
            imageOverlays[currentFront].setZIndex(2);
        }
    }
    bringToFront(0);
    var MyControl = function() {
        var slider;

        function onAdd(map) {
            // create the control container with a particular class name
            var container = L.DomUtil.create('div', 'leaflet-bar leaflet-control slider2-container');
            container.id = 'slider2-container';
            slider_div = L.DomUtil.create('div', 'leaflet-bar-slider2', container);
            slider_div.id = 'slider2';
            slider = noUiSlider.create(slider_div, {
                start: currentFront,
                orientation: 'vertical',
                range: {
                    'min': 0,
                    'max': imageOverlays.length - 1
                },
                step: 1,
                format: {
                    to: function(v) { return Math.floor(v); },
                    from: function(v) { return Number(v); }
                },
                tooltips: [
                    {
                        to: function(x) { return Math.floor(x); }
                    }
                ],
                keyboardDefaultStep: 1
            });
            slider.on('update', function(ev) {
                bringToFront(slider.get());
            });
            L.DomEvent.disableClickPropagation(slider_div);
            container.control = slider;
            return container;
        }

        return L.Control.extend({
            options: {
                position: 'topleft'
            },
            onAdd: onAdd,
        });
    }();
    var slider = new MyControl();
    map.addControl(slider);

    // zoom by wheel
    document.getElementById('map').addEventListener('wheel', function(ev) {
        var s = slider.getContainer().control;
        var position = Math.min(
            Math.max(s.get() - Math.sign(-ev.deltaY), 0),
            imageOverlays.length - 1
        );
        s.set(position);
    });

    return {
        map: map,
        region_layer: region_layer,
        marker_layer: L.layerGroup().addTo(map),
        mid_marker_layer: L.layerGroup().addTo(map),
        region_points: region_points,
    };
}

function wantsToMerge(xray, v, i, region) {
    var lasti = i === 0? region.length - 1 : i - 1;
    var nexti = i === region.length - 1? 0 : i + 1;
    var lastp = xray.map.latLngToLayerPoint(region[lasti]);
    var nextp = xray.map.latLngToLayerPoint(region[nexti]);
    var p = xray.map.latLngToLayerPoint(v);
    return pointsClose(p, lastp, 10) || pointsClose(p, nextp, 10);
}

function mergePoints(xray, i, region, region_index) {
    var r = region.slice(0, i).concat(region.slice(i + 1));
    return xray.region_points.slice(0, region_index).concat(
        r, xray.region_points.slice(region_index + 1));
}

function moveMarker(ev, xray, v, i, region, region_index) {
    v[0] = ev.latlng.lat;
    v[1] = ev.latlng.lng;
    if (wantsToMerge(xray, v, i, region)) {
        xray.region_layer.setLatLngs(mergePoints(xray, i, region, region_index));
    } else {
        xray.region_layer.setLatLngs(xray.region_points);
    }
}

function removeRegionMarkers(xray) {
    xray.marker_layer.clearLayers();
    xray.mid_marker_layer.clearLayers();
}

function addRegionMarkers(xray) {
    var midIcon = L.icon({
        iconUrl: '/static/home/ring.svg',
        iconSize: [20, 20],
        iconAnchor: [10, 10],
    });
    forEach(xray.region_points, function(region, region_index) {
        forEach(region, function(vertex, index) {
            var v = L.marker(vertex, {
                draggable: true,
            }).addTo(xray.marker_layer);
            L.DomEvent.on(v, 'dragstart', function(ev) {
                xray.mid_marker_layer.clearLayers();
            });
            L.DomEvent.on(v, 'drag', function(ev) {
                moveMarker(ev, xray, vertex, index, region, region_index);
            });
            L.DomEvent.on(v, 'dragend', function(ev) {
                if (wantsToMerge(xray, vertex, index, region)) {
                    console.log(xray.region_points);
                    xray.region_points[region_index] = mergePoints(xray, index, region, region_index);
                    console.log(xray.region_points);
                }
                removeRegionMarkers(xray);
                addRegionMarkers(xray);
            });
        });
        forEachInCycle(region, function(v0, v1, i0, i1) {
            var v = [ (v0[0] + v1[0])/2, (v0[1] + v1[1])/2 ];
            var m = L.marker(v, {
                draggable: true,
                icon: midIcon,
            }).addTo(xray.mid_marker_layer);
            L.DomEvent.on(m, 'dragstart', function(ev) {
                region.splice(i1, 0, v);
            });
            L.DomEvent.on(m, 'drag', function(ev) {
                moveMarker(ev, xray, v, i1, region, region_index);
            });
            L.DomEvent.on(m, 'dragend', function(ev) {
                removeRegionMarkers(xray);
                addRegionMarkers(xray);
            });
        });
    });
}

function beginEdit(xray) {
    addRegionMarkers(xray);
    var edit = document.getElementById("edit");
    var save = document.getElementById("save");
    edit.setAttribute('disabled', true);
    save.removeAttribute('disabled');
}

function save(xray) {
    removeRegionMarkers(xray);
    console.log('should do some saving here (remember the csrf token!)');
    var edit = document.getElementById("edit");
    var save = document.getElementById("save");
    edit.removeAttribute('disabled');
    save.setAttribute('disabled', true);
    xray.marker_layer.clearLayers();
}

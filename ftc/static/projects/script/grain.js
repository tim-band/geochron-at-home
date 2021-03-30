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

// lines are as + at*ad and bs + bt*bd (at,bt <- [0,1])
// so at the crossing point: as + at*ad = bs +bt*bd
// separating out co-ordinates (0 and 1 for x and y):
// as0 + at*ad0 = bs0 + bt*bd0
// as1 + at*ad1 = bs1 + bt*bd1
// multiply through by bd1 and bd0
// as0*bd1 + at*ad0*bd1 = bs0*bd1 + bt*bd0*bd1
// as1*bd0 + at*ad1*bd0 = bs1*bd0 + bt*bd1*bd0
// subtracting:
// as0*bd1 - as1*bd0 + at*(ad0*bd1 - ad1*bd0) = bs0*bd1 - bs1*bd0
// `at` on the LHS:
// at*(ad0*bd1 - ad1*bd0) = bs0*bd1 - bs1*bd0 - as0*bd1 + as1*bd0
// at*(ad0*bd1 - ad1*bd0) = bd1 * (bs0 - as0) + bd0 * (as1 - bs1)
// by symmetry a/b:
// bt*(bd0*ad1 - bd1*ad0) = ad1 * (as0 - bs0) + ad0 * (bs1 - as1)
// re-arranging to look like the `a` version:
// bt*(ad0*bd1 - ad1*bd0) = ad1 * (bs0 - as0) + ad0 * (as1 - bs1)
function linesCross(aStart, aEnd, bStart, bEnd) {
    var ad = [aEnd[0] - aStart[0], aEnd[1] - aStart[1]];
    var bd = [bEnd[0] - bStart[0], bEnd[1] - bStart[1]];
    var max = ad[0] * bd[1] - ad[1] * bd[0];
    var min = 0;
    if (max < 0) {
        min = max;
        max = 0;
    }
    var sd0 = bStart[0] - aStart[0];
    var sd1 = aStart[1] - bStart[1];
    var b = bd[1] * sd0 + bd[0] * sd1;
    if (b < min || max < b) {
        return false;
    }
    var a = ad[1] * sd0 + ad[0] * sd1;
    return min <= a && a <= max;
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
    if (region.length < 2) {
        return false;
    }
    var lasti = i === 0? region.length - 1 : i - 1;
    var nexti = i === region.length - 1? 0 : i + 1;
    var lastp = xray.map.latLngToLayerPoint(region[lasti]);
    var nextp = xray.map.latLngToLayerPoint(region[nexti]);
    var p = xray.map.latLngToLayerPoint(v);
    return pointsClose(p, lastp, 10) || pointsClose(p, nextp, 10);
}

function mergePoints(xray, i, region, region_index) {
    if (region.length === 2 && 1 < xray.region_points.length) {
        // gone down to a single point. If there are more regions,
        // just delete the whole region.
        return xray.region_points.slice(0, region_index).concat(
            xray.region_points.slice(region_index + 1));
    }
    var r = region.slice(0, i).concat(region.slice(i + 1));
    var new_regions = xray.region_points.slice(0, region_index).concat(
        [r], xray.region_points.slice(region_index + 1));
    return new_regions;
}

// get a list of sides that cross other sides, sorted by
// their lengths
function getSplits(i, region) {
    var n = region.length;
    if (n < 5) {
        return [];
    }
    // moving sides are i0->i and i->i1
    var i0 = (i + n - 1) % n; // node before i
    var i1 = (i + 1) % n; // node after i
    var cuts = {};
    // iterate through the other non-adjacent sides
    var prev = (i1 + 1) % n;
    for (var j = (prev + 1) % n; j !== i0; prev=j,j=(j+1)%n) {
        if (linesCross(region[i], region[i1], region[prev], region[j])) {
            cuts[i1] = true;
            cuts[j] = true;
        }
        if (linesCross(region[i0], region[i], region[prev], region[j])) {
            cuts[i] = true;
            cuts[j] = true;
        }
    }
    var c = Object.keys(cuts);
    c.sort();
    return c;
}

// get a list of sides in other_region that are crossed by the
// two sides next to node i from home_region
function getSplits2(i, home_region, other_region) {
    var m = home_region.length;
    var n = other_region.length;
    // moving sides are i0->i and i->i1
    var i0 = (i + m - 1) % m; // node before i
    var i1 = (i + 1) % m; // node after i
    var cuts = {};
    var prev = n-1;
    for (var j = 0; j !== n; prev=j, j++) {
        if (linesCross(home_region[i], home_region[i1], other_region[prev], other_region[j])) {
            cuts[j] = true;
        }
        if (linesCross(home_region[i0], home_region[i], other_region[prev], other_region[j])) {
            cuts[j] = true;
        }
    }
    var c = Object.keys(cuts);
    c.sort();
    return c;
}

// return the two biggest parts after slicing before each node
// index in the `splits` array (returns the biggest first, returns
// only one if there is only one part)
function getParts(splits, region, min_parts) {
    if (splits.length < min_parts) {
        return null;
    }
    var lastIndex = splits[splits.length - 1];
    var prev = splits[0];
    var parts = [region.slice(lastIndex).concat(region.slice(0, prev))];
    for (var j = 1, cur=splits[1]; j !== splits.length; prev=cur, ++j, cur=splits[j]) {
        parts.push(region.slice(prev, cur));
    }
    if (parts.length < min_parts) {
        return null;
    }
    parts.sort(function(a,b) {
        return b.length - a.length;
    });
    return parts.slice(0,2);
}

function mergeRegion(home_region, i, other_region) {
    var ps = getParts(getSplits2(i, home_region, other_region), other_region, 1);
    if (!ps) {
        return null;
    }
    return home_region.slice(0, i).concat(
        ps[0],
        home_region.slice(i + 1)
    );
}

function mergeRegions(regions, region_index, region, i) {
    for (var oi = 0; oi !== region_index; ++oi) {
        var other_region = regions[oi];
        var new_region = mergeRegion(region, i, other_region);
        if (new_region) {
            return regions.slice(0, oi).concat(
                [new_region],
                regions.slice(oi + 1, region_index),
                regions.slice(region_index + 1)
            );
        }
    }
    for (var oi = region_index + 1; oi < regions.length; ++oi) {
        var other_region = regions[oi];
        var new_region = mergeRegion(region, i, other_region);
        if (new_region) {
            return regions.slice(0, region_index).concat(
                regions.slice(region_index + 1, oi),
                [new_region],
                regions.slice(oi + 1)
            );
        }
    }
    return regions;
}

function reconfigureRegions(regions, region_index, region, i) {
    var parts = getParts(getSplits(i, region), region, 2);
    if (parts) {
        return regions.slice(0, region_index).concat(
            parts,
            regions.slice(region_index + 1)
        );
    }
    return mergeRegions(regions, region_index, region, i);
}

function moveMarker(ev, xray, v, i, region, region_index) {
    v[0] = ev.latlng.lat;
    v[1] = ev.latlng.lng;
    var new_regions;
    if (wantsToMerge(xray, v, i, region)) {
        new_regions = mergePoints(xray, i, region, region_index);
    } else {
        new_regions = reconfigureRegions(xray.region_points, region_index, region, i);
    }
    xray.region_layer.setLatLngs(new_regions);
    return new_regions;
}

function normalizeRegions(regions) {
    var count = 0;
    forEach(regions, function(region, i) {
        if (2 < region.length) {
            var area = 0;
            var last = region[region.length - 1];
            var r = [];
            forEach(region, function(v) {
                if (v[0] !== last[0] || v[1] !== last[1]) {
                    area += v[0] * last[1] - last[0] * v[1];
                    r.push(v);
                    ++count;
                    last = v;
                }
            });
            if (r.length === 0) {
                // all the points were the same!
                r = [region[0]];
            }
            if (area < 0) {
                r.reverse();
            }
            regions[i] = r;
        } else {
            count += region.length;
        }
    });
    if (count === 0) {
        regions = [[[0.5,0.5]]];
    }
    return regions;
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
    xray.region_points = normalizeRegions(xray.region_points);
    var new_regions;
    forEach(xray.region_points, function(region, region_index) {
        forEach(region, function(vertex, index) {
            var v = L.marker(vertex, {
                draggable: true,
            }).addTo(xray.marker_layer);
            L.DomEvent.on(v, 'dragstart', function() {
                xray.mid_marker_layer.clearLayers();
            });
            L.DomEvent.on(v, 'drag', function(ev) {
                new_regions = moveMarker(ev, xray, vertex, index, region, region_index);
            });
            L.DomEvent.on(v, 'dragend', function() {
                xray.region_points = new_regions;
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
            L.DomEvent.on(m, 'dragstart', function() {
                region.splice(i1, 0, v);
            });
            L.DomEvent.on(m, 'drag', function(ev) {
                new_regions = moveMarker(ev, xray, v, i1, region, region_index);
            });
            L.DomEvent.on(m, 'dragend', function() {
                xray.region_points = new_regions;
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

function save(xray, url, form, error_callback) {
    const xhr = new XMLHttpRequest();
    const fd = new FormData(form);
    forEach(xray.region_points, function(region, ri) {
        forEach(region, function(v, vi) {
            fd.append('vertex_' + ri + '_' + vi + '_x', v[1]);
            fd.append('vertex_' + ri + '_' + vi + '_y', v[0]);
        });
    });
    xhr.addEventListener("load", function() {
        removeRegionMarkers(xray);
        var edit = document.getElementById("edit");
        var save = document.getElementById("save");
        edit.removeAttribute('disabled');
        save.setAttribute('disabled', true);
        xray.marker_layer.clearLayers();
    });
    if (error_callback) {
        xhr.addEventListener("error", function() {
            error_callback();
        });
    }
    xhr.open("POST", url);
    xhr.send(fd);
}

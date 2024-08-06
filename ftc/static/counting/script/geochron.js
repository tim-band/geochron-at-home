/* geochron v0.1 (c) 2014 Jiangping He */
/**
 * Creates a pannable, focusable viewer of a grain z-stack.
 * @param {*} options Options:
 * grain_info.image_height The height in pixels of the image
 * grain_info.image_width The width in pixels of the image
 * grain_info.shift_x The x-difference in pixels of the Mica layers from the crystal layers
 * grain_info.shift_y The y-difference in pixels of the Mica layers from the crystal layers
 * grain_info.scale_x Meters per pixel, if known
 * grain_info.images Array of URLs to the z-stack images
 * grain_info.indices Array of indices corresponding to the images. A contained track will
 *  have its z co-ordinate matching an index in this array.
 * grain_info.marker_latlngs Array of marker positions, instead of `points`
 * grain_info.points Array of marker positions and categories, instead of `marker_latlngs`. Objects with keys:
 * - x_pixels: x position in pixels from the left of the image
 * - y_pixels: y position in pixels from the top of the image
 * - category: string referencing the name (primary key) of the appropriate GrainPointCategory ('track', 'defect' etc.)
 * - comment: arbitrary string describing this particular marker
 * grain_info.rois Array of regions of interest, each of which is an array
 *   of vertex positions [lat,lng] (that is, [(height - y_pixels)/width,
 *   x_pixels/width])
 * grain_info.lengths (optional) Array of fully-contained tracks, each as a three-element
 *  array of [lat,lng,alt] positions of the ends of the track. `alt` is the layer; 0 at the top
 * iconUrl_normal Url of marker image
 * iconSize size of marker image in pixels
 * iconAnchor [x, y] position of anchor on marker image in pixels
 * iconPopup [x, y] position of anchor of popups on marker image in pixels
 * iconUrl_selected url of selected marker image, should be the same size
 *   and shape as iconUrl_normal.
 * iconUrl_comment (optional) marker image with comment tooltip, same size
 *   and shape as iconUrl_normal.
 * only_category only consider points if their category matches this.
 * atoken CSRF token
 * @returns {*} An object giving functions to add functionality to the viewer
 * setTrackCounterCallback: Sets a function that takes the current number of
 *   markers and sets this in some track counter element
 * setTrackCounterElement: as setTrackCounterCallback, but takes an input
 *   element that should have its counter set as a three digit number
 * submitTrackCount: Takes two URLs, submitUrl and newGrainUrl, POSTs the
 *  current marker set to submitUrl and redirects to newGrainUrl
 * saveTrackCount: Takes a URL and POSTs the current marker set to it
 * saveTrackCountIfNecessary: as for saveTrackCount except will do nothing
 *  if the undo stack is in the same state as it was since the last save
 *  (implying that nothing has been changed since then).
 * restartTrackCount: Deletes all the markers and reset the track counter
 * enableEditing: Creates the editing buttons and allows clicking to add markers
 * map: The Leaflet map
 * roisLayer: The Leaflet layer containing the region polygons
 * resetUndo: Deletes the contents of the undo and redo stacks
 * firstMarker: Selects and pans to the first marker
 * nextMarker: Selects and pans to the marker after the one selected, returning
 *  true if there is another one, false if not.
 */
function grain_view(options) {
    // default tile size in Leaflet is 256x256
    var TILE_SIZE = 256;
    var grain_info = options.grain_info;
    var mapZoom = 11;
    var MarkerIcon = L.Icon.extend({
        options: {
            iconSize: options.iconSize,
            iconAnchor: options.iconAnchor,
            popupAnchor: options.iconPopup
        }
    });
    var normalIcon = new MarkerIcon({
        iconUrl: options.iconUrl_normal
    });
    var selectedIcon = new MarkerIcon({
        iconUrl: options.iconUrl_selected
    });
    var commentIcon = null;
    if ('iconUrl_comment' in options) {
        commentIcon = new MarkerIcon({
            iconUrl: options.iconUrl_comment
        })
    }
    var shortcut_map = {};
    document.getElementById('map').addEventListener('keydown', function(ev) {
        if (ev.key in shortcut_map) {
            shortcut_map[ev.key]();
            ev.preventDefault();
        }
    });
    function addShortcut(key, description, fn) {
        shortcut_map[key] = fn;
        var help_list = document.getElementById('help-list');
        if (help_list) {
            var li = document.createElement('li');
            li.textContent = key + ': ' + description;
            help_list.appendChild(li);
        }
    }
    function makeSelector(map, markers, updateMarkerDataFn) {
        var rect = L.rectangle([
            [0., 0.],
            [0., 0.]
        ], {
            className: "ftc-rect-select-area",
            color: "#ff0000",
            fillOpacity: 0,
            stroke: true,
            weight: 2,
            fill: false,
            clickable: true
        });
        var trash_mks_in = [];
        var oneCorner, twoCorner;
        var numClick = 0;
        function resetMarkers() {
            for (var i in trash_mks_in) {
                var indx = trash_mks_in[i]
                if (indx in markers) {
                    var icon = normalIcon;
                    if (markers[indx].marker.options.title) {
                        icon = commentIcon;
                    }
                    markers[indx].marker.setIcon(icon);
                }
            }
            trash_mks_in = [];
            updateMarkerDataFn('', '', 0);
        }
        function deleteSelected() {
            if (trash_mks_in.length !== 0) {
                var mks = {};
                for (var i in trash_mks_in) {
                    var indx = trash_mks_in[i]
                    mks[indx] = markers[indx];
                }
                undo.withUndo(removeFromMap(mks));
                trash_mks_in = [];
                updateMarkerDataFn('', '', 0);
            }
        }
        function stopSelecting() {
            removeClass('ftc-btn-select', 'selecting');
            rect.setBounds([
                [0., 0.],
                [0., 0.]
            ]);
            resetMarkers();
        }
        function updateMarkerData() {
            var category = null;
            var comment = null;
            for (var i in trash_mks_in) {
                var mk = markers[trash_mks_in[i]];
                if (typeof(mk) === 'undefined') {
                    delete markers[trash_mks_in[i]];
                } else if (category === null) {
                    category = mk.category;
                    comment = mk.comment;
                } else {
                    if (category !== mk.category) {
                        category = '';
                    }
                    if (comment !== mk.comment) {
                        comment = '';
                    }
                    if (category === '' && comment === '') {
                        updateMarkerDataFn('', '', trash_mks_in.length);
                        return;
                    }
                }
            }
            updateMarkerDataFn(category, comment, trash_mks_in.length);
        }
        function setDrawRectangle(e) {
            twoCorner = e.latlng;
            rect.setBounds([oneCorner, twoCorner]);
        }
        function setTwoCorner(e) {
            twoCorner = e.latlng;
            rect.setBounds([oneCorner, twoCorner]);
            bounds = L.latLngBounds(oneCorner, twoCorner);
            map.off('mousemove', setDrawRectangle);
            map._container.style.cursor = 'crosshair';
            stopSelecting();
            var j = 0;
            for (var i in markers) {
                var latlng = markers[i].marker.getLatLng();
                if (bounds.contains(latlng)) {
                    trash_mks_in[j] = i;
                    markers[i].marker.setIcon(selectedIcon);
                    j++;
                }
            }
            if (trash_mks_in.length > 0) {
                removeClass('ftc-btn-delete', 'leaflet-disabled');
            } else {
                trash_mks_in = [];
                restoreCounting(e);
            }
            updateMarkerData();
        }
        function setOneCorner(e) {
            //L.DomEvent.preventDefault(e);
            //L.DomEvent.stopPropagation(e);
            oneCorner = e.latlng;
            rect.setBounds([oneCorner, oneCorner]);
            rect.addTo(map).bringToFront();
            map.on('mousemove', setDrawRectangle);
        }
        function drawRectangle(e) {
            numClick++;
            if (numClick == 1) {
                setOneCorner(e);
            } else if (numClick == 2) {
                setTwoCorner(e);
            } else if (numClick == 3) {
                restoreCounting(e);
            } else {
                alert('click event should not listened any more');
            }
        }
        function restoreCounting(e) {
            L.DomEvent.preventDefault(e);
            L.DomEvent.stopPropagation(e);
            map.off('click', drawRectangle);
            map.on('click', onMapClick);
            numClick = 0;
            stopSelecting();
            addClass('ftc-btn-delete', 'leaflet-disabled');
        }
        function selectMarkers(marker_indices) {
            stopSelecting();
            trash_mks_in = marker_indices;
            for (var i in marker_indices) {
                markers[marker_indices[i]].marker.setIcon(selectedIcon);
            }
            updateMarkerData();
        }
        var setting_keys = ['category', 'comment'];
        // data is an object whose keys are indexes into the marker array
        // and whose values are objects whose keys are a subset of
        // { 'category', 'comment' } and whose values are the strings
        // to set. Returns a function that would set it all back.
        function setData(data) {
            var undo_data = {};
            for (var i in data) {
                var o = data[i];
                undo_data[i] = {}
                setting_keys.forEach(function(k) {
                    if (k in o) {
                        undo_data[i][k] = markers[i][k];
                        markers[i][k] = o[k];
                    }
                });
            }
            selectMarkers(Object.keys(data));
            return setData.bind(null, undo_data);
        }
        // Gets the data (category and comment) from each selected element.
        // If the markers disagree the appropriate data values will be null.
        function getData() {
            var out = {};
            for (tmi in trash_mks_in) {
                var m = markers[trash_mks_in[tmi]];
                setting_keys.forEach(function(k) {
                    if (k in m) {
                        if (!(k in out)) {
                            out[k] = m[k];
                        } else if (m[k] !== out[k]) {
                            out[k] = null;
                        }
                    }
                });
            }
            return out;
        }
        function panViewTo(id) {
            map.panTo(markers[id].marker.getLatLng(), {
                animate: true,
                duration: 0.25
            });
        }
        function selectAndPan(id) {
            selectMarkers([id]);
            panViewTo(id);
        }
        return {
            deleteSelected: deleteSelected,
            restoreCounting: restoreCounting,
            drawRectangle: drawRectangle,
            stopSelecting: stopSelecting,
            selectMarkers: selectMarkers,
            setCategory: function(category) {
                var d = {};
                trash_mks_in.forEach(function(i) {
                    d[i] = { category: category };
                });
                undo.withUndo(setData(d));
            },
            setComment: function(comment) {
                var d = {};
                trash_mks_in.forEach(function(i) {
                    d[i] = { comment: comment };
                });
                undo.withUndo(setData(d));
            },
            updateMarkerData: updateMarkerData,
            previousMarker: function() {
                var ids = Object.keys(markers);
                var n = ids.length - 1;
                if (trash_mks_in.length !== 0) {
                    n = ids.indexOf(trash_mks_in[0]) - 1;
                    if (n < 0) {
                        n = ids.length - 1;
                    }
                }
                if (0 <= n) {
                    selectAndPan(ids[n]);
                    return true;
                }
                return false;
            },
            nextMarker: function() {
                var ids = Object.keys(markers);
                var n = 0;
                if (trash_mks_in.length !== 0) {
                    n = ids.indexOf(trash_mks_in[0]) + 1;
                    if (n === ids.length) {
                        n = 0;
                    }
                }
                if (n < ids.length) {
                    selectAndPan(ids[n]);
                    return true;
                }
                return false;
            },
            firstMarker: function() {
                var ids = Object.keys(markers);
                if (0 < ids.length) {
                    selectAndPan([ids[0]]);
                    return true;
                }
                return false;
            },
            getData: getData
        }
    }
    var isEditable = false;
    function makeMarkers(map) {
        var track_id = 0;
        var track_num = 0;
        var markers = {};
        var dragged_out = false;
        var map_window = document.getElementById('map');
        function within_map(x, y) {
            for (const r of map_window.getClientRects()) {
                if (r.left <= x && x < r.right && r.top <= y && y < r.bottom) {
                    return true;
                }
            }
            return false;
        }
        var update_category_and_comment_fn = function(cat, com) {};
        var category_select = document.getElementById('category');
        var comment_text = document.getElementById('comment-text');
        if (category_select && comment_text) {
            update_category_and_comment_fn = function(category, comment, count) {
                category_select.value = category;
                comment_text.value = comment;
                if (comment === '' || comment === null) {
                    removeClass('btn-comment', 'btn-info');
                } else {
                    addClass('btn-comment', 'btn-info');
                }
                var comment_button = document.getElementById('btn-comment');
                if (count === 0) {
                    comment_button.setAttribute('disabled', true);
                    comment_button.setAttribute('aria-disabled', true);
                } else {
                    comment_button.removeAttribute('disabled');
                    comment_button.removeAttribute('aria-disabled');
                }
            };
            addShortcut('c', 'open comment box', function() {
                $('#btn-comment').dropdown('toggle');
            });
            addShortcut('t', 'select mark category', function() {
                $('#category').focus();
            });
        }
        var selector = null;
        return {
            makeSelector: function() {
                selector = makeSelector(
                    map,
                    markers,
                    update_category_and_comment_fn
                );
                return selector;
            },
            // Returns a new track marker with a new track ID,
            // as an object with a single key (the new track ID)
            // with the value as this new marker. This return
            // value can be passed into addToMap as is.
            make: function(latlng, category, comment) {
                var mks = {};
                var startLatLng = null;
                var icon = normalIcon;
                var title = '';
                if (commentIcon && comment) {
                    icon = commentIcon;
                    title = comment;
                }
                var mk = new L.marker(latlng, {
                    icon: icon,
                    draggable: isEditable,
                    riseOnHover: true,
                    className: 'jhe-fissionTrack-' + track_id,
                    title: title
                }).on('click', function() {
                    if (selector && isEditable) {
                        selector.selectMarkers([Object.keys(mks)[0]]);
                    }
                }).on('dragstart', function(e) {
                    dragged_out = false;
                    startLatLng = e.target.getLatLng();
                }).on('drag', function(e) {
                    var out = dragged_out;
                    var dragged_out_of_screen = !within_map(e.originalEvent.clientX, e.originalEvent.clientY);
                    dragged_out = dragged_out_of_screen || !zStack.pointInRois(e.latlng.lat, e.latlng.lng);
                    if (out) {
                        if (!dragged_out) {
                            mk.setOpacity(1)
                        }
                    } else if (dragged_out) {
                        mk.setOpacity(0.5)
                    }
                }).on('dragend', function(e) {
                    // delete if we are outside of the ROI
                    if (dragged_out) {
                        mk.setOpacity(1)
                        mk.setLatLng(startLatLng);
                        undo.withUndo(removeFromMap(mks));
                    } else {
                        // we already did this move, but we need to make it part of the
                        // undo stack
                        undo.withUndo(moveMarker(mk, startLatLng, e.target.getLatLng()));
                    }
                });
                mks[track_id] = {
                    marker: mk,
                    category: category,
                    comment: comment
                };
                track_id++;
                return mks;
            },
            /**
             * Add markers to map.
             * @param markersToAdd map from track_id to object with a `marker` key
             */
            addToMap: function(markersToAdd) {
                for (var k in markersToAdd) {
                    mk = markersToAdd[k];
                    mk.marker.setIcon(normalIcon);
                    mk.marker.addTo(map);
                    markers[k] = mk;
                    track_num += 1;
                }
                selector.selectMarkers(
                    Object.keys(markersToAdd)
                );
            },
            /**
             * Remove markers from map.
             * @param markersToRemove map from track_id to object with a `marker` key
             */
            removeFromMap: function(markersToRemove) {
                for (var k in markersToRemove) {
                    map.removeLayer(markersToRemove[k].marker);
                    delete markers[k];
                    track_num = track_num - 1;
                }
                selector.updateMarkerData();
            },
            removeAllFromMap: function() {
                var mks = {};
                for (var k in markers) {
                    mks[k] = markers[k];
                }
                removeFromMap(mks);
                selector.updateMarkerData();
                return mks;
            },
            getLatLngs: function() {
                var latlngs = new Array();
                for (var i in markers) {
                    latlng = markers[i].marker.getLatLng();
                    latlngs.push( [latlng.lat, latlng.lng] );
                }
                return latlngs;
            },
            getPoints: function() {
                var ps = new Array();
                var width = grain_info.image_width;
                var height = grain_info.image_height;
                for (var i in markers) {
                    latlng = markers[i].marker.getLatLng();
                    ps.push({
                        'x_pixels': latlng.lng * width,
                        'y_pixels': height - latlng.lat * width,
                        'category': markers[i].category,
                        'comment': markers[i].comment
                    });
                }
                return ps;
            },
            trackCount: function() {
                return track_num;
            },
            empty: function() {
                for (var i in markers) {
                    return false;
                }
                return true;
            }
        };
    }
    // find x in array of increasing numbers, returning an interpolated index
    // depending on how close x is to its neighbouring values:
    // findInMonotonic(5, [3,4,5,6]) => 2
    // findInMonotonic(5, [2,4,6,8]) => 1.5
    function findInMonotonic(x, xs) {
        if (xs.length < 2 || x < xs[0]) {
            return 0;
        }
        for (var i = 1; i != xs.length; ++i) {
            if (x < xs[i]) {
                // line (X,Y) through (i - 1, xs[i - 1]) and (i, xs[i])
                // is Y = xs[i - 1] + (X - (i-1)) * (xs[i] - xs[i-1])
                // we want X in terms of Y
                // Y - xs[i-1] = (X - (i-1)) * (xs[i] - xs[i-1])
                // (Y - xs[i-1]) / (xs[i] - xs[i-1]) = X - (i-1)
                // X = (Y - xs[i-1]) / (xs[i] - xs[i-1]) + i - 1
                // X = (Y - xs[i-1]) / (xs[i] - xs[i-1]) + i - ((xs[i] - xs[i-1]) / (xs[i] - xs[i-1]))
                // X = (Y - xs[i-1] - (xs[i] - xs[i-1])) / (xs[i] - xs[i-1]) + i
                // X = (Y - xs[i-1] - xs[i] + xs[i-1]) / (xs[i] - xs[i-1]) + i
                // X = (Y - xs[i]) / (xs[i] - xs[i-1]) + i
                return (x - xs[i]) / (xs[i] - xs[i-1]) + i;
            }
        }
        return xs.length - 1;
    }
    function makeLengthMarkers(map) {
        var track_id = 0;
        var markers = [];
        var radius = 20;
        function focusEnd(mk, layer_diff) {
            var abs_diff = Math.abs(layer_diff);
            var weight = abs_diff * 5 + 3;
            mk.setStyle({
                weight: weight,
                color: 0 < layer_diff? '#308050' : '#60a090',
                opacity: 9 / weight
            });
        }
        function focus(layer) {
            markers.forEach(function(marker) {
                focusEnd(marker.end1, layer - marker.layer1);
                focusEnd(marker.end2, layer - marker.layer2);
            });
        }
        return {
            makeAndShow: function(latlng1, latlng2) {
                var layer1 = findInMonotonic(latlng1[2], grain_info.indices);
                var layer2 = findInMonotonic(latlng2[2], grain_info.indices);
                var mk1 = new L.circleMarker(latlng1, {
                    radius: radius,
                    interactive: false,
                    className: `contained-track-${track_id}-1`
                }).addTo(map);
                var mk2 = new L.circleMarker(latlng2, {
                    radius: radius,
                    interactive: false,
                    className: `contained-track-${track_id}-2`
                }).addTo(map);

                var line = L.polyline([latlng1, latlng2], {
                    color: 'green',
                    weight: 2 * radius,
                    opacity: 0.3
                }).addTo(map);
                markers.push({
                    end1: mk1,
                    end2: mk2,
                    line: line,
                    layer1: layer1,
                    layer2: layer2
                });
                ++track_id;
                focus(0);
            },
            focus: focus
        };
    }
    /**
     * Sets the position and zoom of the view so that the region(s)
     * are as large as they can be in the window (with a little margin).
     * fit_region_to_window(true) animates the zoom and pan, whereas
     * fit_region_to_window(false) snaps it to the home position
     * immediately.
     */
    var fit_region_to_window = function() {
        var minx = Infinity, miny = Infinity;
        var maxx = -Infinity, maxy = -Infinity;
        grain_info.rois.forEach(function(roi) {
            roi.forEach(function(v) {
                minx = Math.min(minx, v[1]);
                miny = Math.min(miny, v[0]);
                maxx = Math.max(maxx, v[1]);
                maxy = Math.max(maxy, v[0]);
            });
        });
        var map_window = document.getElementById('map');
        var scale_to_fit_height = map_window.clientHeight / (maxy - miny);
        var scale_to_fit_width = map_window.clientWidth / (maxx - minx);
        return function(animate) {
            map.setView(
                [
                    (maxy + miny) / 2,
                    (maxx + minx) / 2
                ],
                // multiplying by TILE_SIZE here feels wrong, but seems to produce
                // decent results
                L.CRS.zoom(Math.min(scale_to_fit_height, scale_to_fit_width) * TILE_SIZE),
                { animate: animate }
            );
        }
    }();
    var markers = null;
    var selector = null;
    var buttons = {
        'homeView': {
            icon: 'fa-arrows-alt',
            tipText: 'fit images to window',
            action: function() {
                fit_region_to_window(true);
            }
        },
        'undo': {
            icon: 'fa-history',
            tipText: 'undo',
            className_a: 'leaflet-disabled',
            action: function() {
                undo.undo();
            }
        },
        'redo': {
            icon: 'fa-repeat',
            tipText: 'redo',
            className_a: 'leaflet-disabled',
            action: function() {
                undo.redo();
            }
        },
        'select': {
            icon: 'fa-pencil-square-o',
            tipText: 'click twice to draw a rectangle and select multiple markers',
            action: function(e) {
                if (!hasClass('ftc-btn-select', 'selecting')) {
                    addClass('ftc-btn-select', 'selecting');
                    map.off('click', onMapClick);
                    map._container.style.cursor = 'crosshair';
                    map.on('click', selector.drawRectangle);
                } else {
                    removeClass('ftc-btn-select', 'selecting');
                    selector.restoreCounting(e);
                }
            }
        },
        'delete': {
            icon: 'fa-trash-o',
            tipText: 'delete selected fission track markers',
            className_a: 'leaflet-disabled',
            action: function(e) {
                selector.deleteSelected();
                selector.restoreCounting(e);
            }
        }
    };

    function makeUndoStack() {
        var undoStack = [];
        var redoStack = [];
        // length of undoStack when saved
        var cleanState = 0;
        function execute(fromStack, toStack) {
            if (fromStack.length) {
                var f = fromStack.pop();
                toStack.push(f());
            }
        }
        function updateStackButton(stack, id) {
            if (stack.length) {
                removeClass(id, 'leaflet-disabled');
            } else {
                addClass(id, 'leaflet-disabled');
            }
        }
        function updateUndoRedoButtons() {
            updateStackButton(undoStack, 'ftc-btn-undo');
            updateStackButton(redoStack, 'ftc-btn-redo');
        }
        return {
            redo: function() {
                execute(redoStack, undoStack);
                updateUndoRedoButtons();
            },
            undo: function() {
                execute(undoStack, redoStack);
                updateUndoRedoButtons();
            },
            withUndo: function(f) {
                undoStack.push(f);
                redoStack = [];
                updateUndoRedoButtons();
            },
            updateButtons: updateUndoRedoButtons,
            isClean: function() {
                return cleanState == undoStack.length;
            },
            setClean: function() {
                cleanState = undoStack.length;
            },
            reset: function() {
                undoStack = [];
                redoStack = [];
                cleanState = 0;
            }
        };
    }
    var undo = makeUndoStack();

    function addClass(id, cls) {
        var e = L.DomUtil.get(id);
        if (e) {
            L.DomUtil.addClass(e, cls);
        }
    }
    function removeClass(id, cls) {
        var e = L.DomUtil.get(id);
        if (e) {
            L.DomUtil.removeClass(e, cls);
        }
    }
    function hasClass(id, cls) {
        var e = L.DomUtil.get(id);
        return e && L.DomUtil.hasClass(e, cls);
    }

    var updateTrackCounter = function() {};

    function addToMap(markersToAdd) {
        markers.addToMap(markersToAdd);
        updateTrackCounter();
        return function() { return removeFromMap(markersToAdd); }
    }

    function removeFromMap(markersToRemove) {
        markers.removeFromMap(markersToRemove);
        updateTrackCounter();
        return function() { return addToMap(markersToRemove); }
    }

    function removeAllFromMap() {
        var deleted = markers.removeAllFromMap();
        updateTrackCounter();
        return function() { return addToMap(deleted); }
    }

    function createMarker(latlng, category, comment) {
        var mks = markers.make(latlng, category, comment);
        undo.withUndo(addToMap(mks));
    }

    // fn(create, v, k) takes a function create, an element v of array or object arr
    // and the index (or key) of v in arr. If it wants to create any markers, it calls
    // create(latlng, category, comment) as many times as it likes. All the markers
    // are added in a single operation.
    function forEachCreateMarker(arr, fn) {
        var mks = {};
        for (var k in arr) {
            fn(function(latlng, category, comment) {
                var mks_new = markers.make(latlng, category, comment);
                for (var id in mks_new) {
                    mks[id] = mks_new[id];
                }
            }, arr[k], k);
        }
        undo.withUndo(addToMap(mks));
    }

    function moveMarker(mk, fromLatLng, toLatLng) {
        mk.setLatLng(toLatLng);
        return function() { return moveMarker(mk, toLatLng, fromLatLng); };
    }


    function onMapClick(e) {
        L.DomEvent.preventDefault(e);
        L.DomEvent.stopPropagation(e);
        if (isEditable && zStack.pointInRois(e.latlng.lat, e.latlng.lng)) {
            createMarker(e.latlng, 'track', '');
        }
    };

    function makeZStack(
        map, images, imageCount, yOverX, rois
    ) {
        // Callbacks for when the focused layer changes
        var focus_callbacks = [];
        // Bounds elements are LatLng values, i.e. [y, x]
        var bounds = [
            [0.0, 0.0],
            [yOverX, 1.0]
        ];
        var imageOverlayers = new Array();
        for (var i = 0; i < images.length; i++) {
            imageOverlayers[i] = new L.imageOverlay(
                images[i], bounds
            ).addTo(map);
            imageOverlayers[i].getElement().classList.add("image-crystal");
        }
        var layerCurrent = 0;
        var layerRendered = 0;
        // Try to ensure images are in the cache so appear instantly, unsure of a better solution
        setTimeout(function() {
            imageOverlayers.forEach(function(imageOverlay, i) {
                if (imageOverlay && i !== layerRendered) {
                    imageOverlay.removeFrom(map);
                }
            });
        }, 1000);
        var rois_layer = L.polygon(rois, {
            color: 'white',
            opacity: 1.0,
            fill: false,
            clickable: true,
            className: 'ftc-rect-select-area',
            renderer: L.svg({ padding: 1.0 }), // Prevent SVG paths from being visibly clipped while dragging
        }).on('click', function(e) {
            L.DomEvent.preventDefault(e);
            L.DomEvent.stopPropagation(e);
        }).addTo(map);
        function point_in_polygon(x, y, vs) {
            // ray-casting algorithm based on
            // http://www.ecse.rpi.edu/Homepages/wrf/Research/Short_Notes/pnpoly.html
            var inside = false;
            for (var i = 0, j = vs.length - 1; i < vs.length; j = i++) {
                var xi = vs[i][0],
                    yi = vs[i][1];
                var xj = vs[j][0],
                    yj = vs[j][1];
                var intersect = ((yi > y) != (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
                if (intersect) inside = !inside;
            }
            return inside;
        };
        function point_in_odd_number_of_polygons(x, y, vss) {
            var count = 0;
            for (var i =0; i !== vss.length; ++i) {
                if (point_in_polygon(x, y, vss[i])) {
                    count += 1;
                }
            }
            return (count % 2) === 1;
        }
        function add_current_layer() {
            if (layerRendered < imageOverlayers.length) {
                imageOverlayers[layerRendered].addTo(map);
            }
        }
        function remove_current_layer() {
            if (layerRendered < imageOverlayers.length) {
                imageOverlayers[layerRendered].removeFrom(map);
            }
        }
        function refresh() {
            remove_current_layer();
            layerRendered = layerCurrent;
            add_current_layer();
            focus_callbacks.forEach(function(fn) {
                fn(layerRendered);
            });
        }
        refresh();
        return {
            set: function(position) {
                layerCurrent = position;
                refresh();
            },
            position: function() {
                return layerCurrent;
            },
            decrement: function() {
                layerCurrent = 0 < layerCurrent? layerCurrent - 1 : 0;
                refresh();
            },
            increment: function() {
                var c = layerCurrent + 1;
                layerCurrent = c < imageCount? c : imageCount - 1;
                refresh();
            },
            pointInRois: function(x, y) {
                // If there are no ROI regoins, we will say every point
                // is in the ROI, otherwise none will be visible.
                if (rois.length === 0) {
                    return true;
                }
                return point_in_odd_number_of_polygons(x, y, rois);
            },
            // Add a function taking an integer, returning nothing.
            // This function will be called with the current layer index
            // whenever this changes.
            addFocusCallback: function(callback) {
                focus_callbacks.push(callback);
            },
            rois_layer: rois_layer
        };
    }

    var zStack = null;

    var map = L.map('map', {
        center: [grain_info.image_height / grain_info.image_width / 2, 0.5],
        zoomSnap: 0,
        zoomDelta: 0.5,
        zoom: mapZoom,
        minZoom: mapZoom - 2,
        maxZoom: mapZoom + 3,
        scrollWheelZoom: false,
        doubleClickZoom: false
    });
    map.attributionControl.setPrefix(''); // Don't show the 'Powered by Leaflet' text.
    map.on('click', onMapClick);

    function focusUp() {
        zStack.decrement();
        sliders2.set(zStack.position());
    }
    function focusDown() {
        zStack.increment();
        sliders2.set(zStack.position());
    }
    L.DomEvent.on(map.getContainer(), 'wheel', function(e) {
        if (e.deltaY < 0) {
            focusUp();
        } else {
            focusDown();
        }
        return false;
    });
    addShortcut('[', 'Focus up', focusUp);
    addShortcut(']', 'Focus down', focusDown);

    var UScale = L.Control.extend({
        options: {
            position: 'bottomleft',
            maxWidth: 100,
            imageWidthMeters: 1e-4,
        },

        onAdd: function (map) {
            map.on('move', this._update, this);
            map.whenReady(this._update, this);

            this.scale = document.createElement('div');
            this.scale.className = 'ftc-uscale-line-10';
            var container = document.createElement('div');
            container.className = 'ftc-uscale';
            container.appendChild(this.scale);  
            return container;
        },

        onRemove: function (map) {
            map.off('move', this._update, this);
        },

        _update: function () {
            if (!this.scale) {
                return;
            }
            var map = this._map;
            var y = map.getSize().y / 2;
            var maxLng =
                map.containerPointToLatLng([this.options.maxWidth, y]).lng -
                map.containerPointToLatLng([0, y]).lng;
            var maxMeters = this.options.imageWidthMeters * maxLng;
            this._updateMetric(maxMeters);
        },

        _updateMetric: function (maxMeters) {
            var unit = ' nm';
            var m = maxMeters / 1e-9;
            if (1000.0 <= m) {
                unit = ' \xB5m';
                m = maxMeters / 1e-6;
                if (1000.0 <= m) {
                    unit = ' mm';
                    m = maxMeters / 1e-3;
                }
            }
            var z = 1;
            while (10.0 <= m) {
                z *= 10;
                m /= 10.0;
            }
            var ratio = 1/m;
            var num = z;
            if (5.0 <= m) {
                num = 5 * z;
                ratio = 5/m;
                this.scale.className = 'ftc-uscale-line-5';
            } else if (2.0 <= m) {
                num = 2 * z;
                ratio = 2/m;
                this.scale.className = 'ftc-uscale-line-2';
            } else {
                this.scale.className = 'ftc-uscale-line-10';
            }
            this.scale.style.width = Math.round(this.options.maxWidth * ratio) + 'px';
            this.scale.innerHTML = num + unit;
        },
    });

    /**************************
     *   slider and tooltip   *
     **************************/
    var FocusControl = L.Control.extend({
        options: {
            position: 'topleft'
        },

        onAdd: function(map) {
            // create the control container with a particular class name
            var container = L.DomUtil.create('div', 'leaflet-bar leaflet-control focus-slider-container');
            container.setAttribute('style', 'margin-left: 14px;margin-top: 27px;');
            this.slider_div = L.DomUtil.create('div', 'leaflet-bar-focus-slider', container);
            this.slider_div.id = 'focus-slider';
            this.slider_div.setAttribute('style', 'height:120px');
            return container;
        }
    });
    map.addControl(new FocusControl());

    if ('scale_x' in grain_info && grain_info.scale_x) {
        map.addControl(new UScale({
            position: 'bottomright',
            maxWidth: 300,
            imageWidthMeters: grain_info.scale_x * grain_info.image_width
        }));
    }

    var focusSliderElt = document.getElementById('focus-slider');
    var sliders2 = noUiSlider.create(focusSliderElt, {
        start: 0,
        orientation: 'vertical',
        range: {
            'min': 0,
            'max': 1
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

    sliders2.on('slide', function(ev) {
        zStack.set(sliders2.get());
    });

    focusSliderElt.onpointerdown = function(ev) {
        // Prevents the sample image from being dragged around
        // by movements that begin on the slider.
        ev.stopPropagation();
    };

    focusSliderElt.onclick = function(ev) {
        // Prevents points from being added
        // by movements that begin on the slider.
        ev.stopPropagation();
    };

    var sliderNum = Math.max(
        grain_info.images.length,
        2
    );
    sliders2.updateOptions({
        range: {
            'min': 0,
            'max': sliderNum - 1
        }
    }, true);
    var width = grain_info.image_width;
    var height = grain_info.image_height;
    var yOverX = height / width;
    zStack = makeZStack(
        map, grain_info.images, sliderNum, yOverX, grain_info.rois
    );
    markers = makeMarkers(map);
    selector = markers.makeSelector();
    lengthMarkers = makeLengthMarkers(map);
    if (lengthMarkers && 'lengths' in grain_info) {
        grain_info.lengths.forEach(lens =>
            lengthMarkers.makeAndShow(lens[0], lens[1])
        );
        zStack.addFocusCallback(lengthMarkers.focus);
    }
    var category_select = document.getElementById('category');
    if (category_select) {
        category_select.onchange = function() {
            selector.setCategory(category_select.value);
        };
        category_select.addEventListener('keydown', function(ev) {
            if (ev.key === 'Enter') {
                $('#map').focus();
            }
        });
    }
    var comment_form = document.getElementById('form-comment');
    var comment_text = document.getElementById('comment-text');
    if (comment_form && comment_text) {
        comment_form.onsubmit = function(ev) {
            selector.setComment(comment_text.value);
            $('#btn-comment').dropdown('toggle');
            $('#map').focus();
            ev.preventDefault();
        };
        document.getElementById('control-comment').addEventListener('keydown', function(ev) {
            if (ev.key === 'Escape') {
                $('#btn-comment').dropdown('toggle');
                $('#map').focus();
            }
        });
        $('#btn-prev-marker').on('click',function() {
            selector.previousMarker();
            $('#map').focus();
        });
        $('#btn-next-marker').on('click',function() {
            selector.nextMarker();
            $('#map').focus();
        });
        addShortcut('p', 'select previous marker', selector.previousMarker);
        addShortcut('n', 'select next marker', selector.nextMarker);
    }
    if ('points' in grain_info) {
        var point_filter = function(point) { return true; };
        if ('only_category' in options) {
            var cat = options.only_category;
            point_filter = function(point) {
                return point.category == cat;
            };
        }
        forEachCreateMarker(grain_info.points, function(create, point) {
            if (point_filter(point)) {
                var lat = (height - point.y_pixels) / width;
                var lng = point.x_pixels / width;
                if (zStack.pointInRois(lat, lng)) {
                    create([lat, lng], point.category, point.comment);
                }
            }
        });
        undo.reset();
    } else if ('marker_latlngs' in grain_info) {
        forEachCreateMarker(grain_info.marker_latlngs, function(create, latlng) {
            create(latlng, 'track', '');
        });
        undo.reset();
    }
    selector.stopSelecting();
    fit_region_to_window(false);

    function setTrackCounterCallback(cb) {
        updateTrackCounter = function() {
            cb(markers.trackCount());
        };
        updateTrackCounter();
    }

    function doSave(url, go_to) {
        var xhr = new XMLHttpRequest();
        xhr.open('POST', url);
        xhr.onload = function() {
            console.log('submitted: ' + xhr.responseText);
            undo.setClean();
            if (go_to) {
                window.location = go_to;
            }
        };
        xhr.onerror = function() {
            console.log(xhr.status + ": " + xhr.responseText);
            alert('Save failed, please try again.');
        };
        xhr.setRequestHeader('X-CSRFToken', options.atoken);
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.send(JSON.stringify({
            'sample_id': grain_info.sample_id,
            'grain_num': grain_info.grain_num,
            'ft_type': grain_info.ft_type,
            'image_width': grain_info.image_width,
            'image_height': grain_info.image_height,
            'marker_latlngs': markers.getLatLngs(),
            'points': markers.getPoints(),
        }));
    }

    function saveTrackCount(url, go_to) {
        if (confirm("Save the intermediate result to the server?")) {
            doSave(url, go_to);
        }
    }

    return {
        setTrackCounterCallback: setTrackCounterCallback,
        setTrackCounterElement: function(element) {
            setTrackCounterCallback(function(count) {
                var v = (1000 + count).toString().slice(1);
                element.setRangeText(v, 0, 3, 'end');
            });
        },
        submitTrackCount: function(update_url, new_grain_url) {
            if (confirm("submit the result?")) {
                doSave(update_url, new_grain_url);
            } else {
                console.log("You pressed Cancel!");
            }
        },
        saveTrackCount: saveTrackCount,
        saveTrackCountIfNecessary: function(save_url, go_to) {
            if (!undo.isClean()) {
                saveTrackCount(save_url, go_to);
            } else if (go_to) {
                window.location = go_to;
            }
        },
        cancelWithConfirm: function(go_to) {
            if (undo.isClean() || confirm("Discard changes?")) {
                window.location = go_to;
            }
        },
        restartTrackCount: function() {
            if (confirm("Are you sure that you want to reset the counter for this grain?")) {
                if (!markers.empty()) {
                    undo.withUndo(removeAllFromMap());
                }
                fit_region_to_window(true);
            }
        },
        enableEditing: function() {
            isEditable = true;
            buttonControl = L.easyButton(buttons, map, 'topright');
            buttonControl.getContainer().addEventListener('dblclick', function(e) {
                e.stopPropagation();
            });
            undo.updateButtons();
        },
        map: map,
        roisLayer: zStack.rois_layer,
        resetUndo: function() {
            undo.reset();
        },
        firstMarker: function() {
            return selector.firstMarker();
        },
        nextMarker: function() {
            return selector.nextMarker();
        },
        getData: function() {
            return selector.getData();
        }
    }
}

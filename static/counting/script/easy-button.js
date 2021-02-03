/* Ref:
1. https://github.com/CliffCloud/Leaflet.EasyButton/blob/master/easy-button.js#L11
2. https://github.com/brunob/leaflet.fullscreen/blob/master/index.html
*/
/*
'topleft'	Top left of the map.
'topright'	Top right of the map.
'bottomleft'	Bottom left of the map.
'bottomright'	Bottom right of the map.
*/
L.Control.EasyButtons = L.Control.extend({
    options: {
        position: 'topright',
        setting: {},	
    },

    initialize: function (position) {
        this.options.position = position;
    },
	
    onAdd: function () {
        var container = L.DomUtil.create('div', 'leaflet-bar leaflet-control');
		
		$.each(this.options.setting, function(name, val){
                        className = 'leaflet-bar-part';
                        if (val.className_a) { 
                            className = className + ' ' + val.className_a;
                        }
                        this.link = L.DomUtil.create('a', className, container);
			this.link.href = '#';
			this.link.title = val.tipText;
                        this.link.id = 'ftc-btn-' + name;

                        className = 'fa ' + val.icon;
                        if (val.className_i) { className = className + ' ' + val.className_i; }
			L.DomUtil.create('i', className, this.link);

			L.DomEvent
		        .addListener(this.link, 'click', L.DomEvent.stopPropagation)
			.addListener(this.link, 'click', L.DomEvent.preventDefault)
			.addListener(this.link, 'click', val.action);
		});
                
        return container;
    },
    
});

L.easyButton = function( btnSetting, btnMap, btnPosition ) {
  if(!btnPosition){
    btnPosition = 'topright';
  }

  var newControl = new L.Control.EasyButtons(btnPosition);

  if(!$.isEmptyObject(btnSetting)) {
    newControl.options.setting = btnSetting;
  }
  if ( btnMap ){
    newControl.addTo(btnMap);
  } else {
    newControl.addTo(map);
  }

  return newControl;
};

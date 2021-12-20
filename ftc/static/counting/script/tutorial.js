$(function() {

    var ft = new FT();

    ft.displaySample(-1);

    $("#samplename").html(ft.getSample().dir);

    $("#grainnum").html(ft.grainnum + 1 + "/" + ft.getSample().grains.length);

    $("#n").html(0);

    $("#slider").slider({
	'orientation': 'vertical',
	'value': 14,
	'min': -1,
	'max': 14,
	'slide': function(e, ui){
	    ft.displaySample(13-ui.value);
	}
    });

    $("#FTimage").click(function (ev) {
	xx = ev.pageX;
	yy = ev.pageY;
	ft.getGrain().X.push(xx);
	ft.getGrain().Y.push(yy);
	ft.getGrain().Ns = ft.getGrain().X.length;
	$("div#n").html(ft.getGrain().Ns);
	plot(xx,yy);
    });

    $("#previous").click(function (ev){
	if (ft.grainnum>0){
	    ft.grainnum--;
	} else if (ft.samplenum>0){
	    ft.samplenum--;
	    ft.grainnum = ft.getSample().grains.length-1;
	}
    $("#next").removeAttr("disabled");
    if (ft.samplenum == 0 && ft.grainnum == 0) {
        $("#previous").attr("disabled", true);
    }
	clearCanvas();
	ft.displaySample(-1);
    var slider = $("#slider");
	if (ft.getSample().slider){
        slider.slider("option", "value", slider.slider("option", "max"));
        slider.show();
	} else {
	    slider.hide();
	}
    });

    $("#next").click(function (ev){
	numgrains = ft.getSample().grains.length;
	if (ft.grainnum<numgrains-1) {
	    ft.grainnum++;
	} else if (ft.samplenum<ft.samples.length-1) {
	    ft.samplenum++;
	    ft.grainnum = 0;
	}
    $("#previous").removeAttr("disabled");
    if (ft.samplenum == ft.samples.length - 1 && ft.grainnum == numgrains - 1) {
        $("#next").attr("disabled", true);
        $("#finish").removeAttr("disabled");
    }
	clearCanvas();
	ft.displaySample(-1);
    var slider = $("#slider");
	if (ft.getSample().slider){
        slider.slider("option", "value", slider.slider("option", "max"));
	    slider.show();
	} else {
	    slider.hide();
	}
    });

    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            xhr.setRequestHeader('X-CSRFToken', atoken);
        }
    });

    $("#finish").click(function(ev) {
        $.ajax({
            url: tutorialResult_url,
            type: 'POST',
            dataType: 'text',
            success: function(result) {
                console.log('submitted tutorial result' );
                window.location.href = return_url;
            },
            error: function(xhr, errmsg, err) {
                console.log(xhr.status + ": " + xhr.responseText);
            }
        });
    });

    function clearCanvas(){
	var c = document.getElementById("myCanvas");
	var ctx = c.getContext("2d");
	ctx.clearRect(0, 0, c.width, c.height);
	ctx.beginPath();
    }

    $("#reflected").click(function (ev){
	if ($("#reflected").text()=='Reflected'){
	    $("#reflected").html('Transmitted');
	    $("#focus").hide();
	    ft.displaySample(1000);
	} else {
	    $("#reflected").html('Reflected');
	    $("#focus").show();
	    ft.displaySample(-1);
	}
    });

    $("#calculate").click(function (ev){
	var ageErr = [];
	var results = "";
	var sample = ft.getSample();
	results += "Sample " + sample.dir + "<br />";
	for (var i=0; i<sample.grains.length; i++){
	    ageErr = ft.getAgeErr(i);
	    results += "Grain " + (i+1) + ": " + (ageErr[0]/1e6).toFixed(2) +
		" +/- " + (ageErr[1]/1e6).toFixed(2) + " Ma <br />";
	}
	$("#results").html(results);
	$("#results").show();
    });

    function FT(){
	this.lambda_d = 0.000000000155125;
	this.dir = tutorialDir + '/';
	this.samples = loadSamples();
	this.samplenum = 0;
	this.grainnum = 0;

	this.getGrain =  function(){
	    return this.getSample().grains[this.grainnum];
	}

	this.getSample = function(){
	    return this.samples[this.samplenum];
	}

	this.getFileName = function(layer){
	    var fname = this.dir + this.getSample().dir + "/" + this.getGrain().dir + "/";
	    if (layer>100) {
		fname += "ReflStackFlat.jpeg";
	    } else {
		fname += "Stack-" + layer + ".jpeg";
	    }
	    return fname;
	}

	this.drawROI = function(ctx, ROI){

	}

	this.displaySample = function(layer){
	    var c = document.getElementById("myCanvas");
	    var ctx = c.getContext("2d");
	    ctx.strokeStyle = '#00ff00';
	    ctx.lineWidth = 3;
	    var img = new Image();
	    var ROIs = this.getGrain().ROIs;
	    var ROI = [];
	    img.src = this.getFileName(layer);
	    img.onload = function(){
		var w = 1024;
		var h = w*img.height/img.width;
		c.width = w;
		c.height = h;
		ctx.drawImage(img,0,0,w,h);
		for (i = 0; i < ROIs.length; i++){
		    ROI = ROIs[i];
		    for (j = 0; j < ROI[0].length-1; j++){
			ctx.moveTo(ROI[0][j],ROI[1][j]);
			ctx.lineTo(ROI[0][j+1],ROI[1][j+1]);
			ctx.stroke();
		    }
		}
	    }
	    $("#results").html(this.getGrain().text);
	}

	this.plotCounts = function(){
	    for (var i=0; i<this.getGrain().X.length; i++){
		plot(this.getGrain().X[i],this.getGrain().Y[i]);
	    }
	}

	this.getAgeErr = function(n){
	    var ageErr = new Array(2);
	    var theSample = this.getSample();
	    var theGrain = theSample.grains[n];
	    var rhoS = theGrain.Ns/theGrain.area;
	    ageErr[0] = Math.log(1+this.lambda_d*theSample.zeta*rhoS/theGrain.U)/this.lambda_d;
	    ageErr[1] = ageErr[0]*Math.sqrt(1/theGrain.Ns +
					    (theGrain.Uerr/theGrain.U)*(theGrain.Uerr/theGrain.U));
	    return ageErr;
	}
    }

    function plot(xx,yy){
	var size = 10;
	var color = '#FFFF00';
        $("body").append(
            $('<div class="added"></div>')
                .css('position', 'absolute')
                .css('top', yy-0.5*size+'px')
                .css('left', xx-0.5*size+'px')
                .css('width', size+'px')
                .css('height', size+'px')
                .css('background-color', color)
        );
    }

    function sample(folder,slider){
	this.dir = folder;
	this.grains = [];
	this.slider = slider;
    }

    function grain(folder,ROIs,text){
	this.dir = folder;
	this.ROIs = ROIs;
	this.text = text;
    }

    function loadSamples(){

	var samples = [new sample('1X',true),
		       new sample('LU324-2-DUR',true),
		       new sample('screenshots',false)];

	samples[0].grains = [new grain('Grain13',
				       [[[],[]]],
				       'This is an apatite crystal which has been polished and etched with acid to reveal the damage tracks caused by the spontaneous fission of naturally occurring uranium. The geological age of the mineral can be determined by counting the number of fission tracks per unit area. The uranium concentration is measured separately. Geochron@home is a crowd-sourcing app to count fission tracks. <b>Move the slider up and down change the focus</b>, in reflected light (top image) and transmitted light (bottom).'),
			     new grain('Grain13',
				       [[[239,451,757,811,682,440,284,176,239],[698,783,645,464,263,317,434,593,698]],[[315,315,339,339,315],[600,624,624,600,600]],[[322,322,346,346,322],[564,588,588,564,564]],[[248,248,272,272,248],[478,502,502,478,478]],[[385,385,409,409,385],[445,469,469,445,445]],[[506,506,530,530,506],[384,408,408,384,384]],[[548,548,572,572,548],[298,322,322,298,298]],[[708,708,732,732,708],[557,581,581,557,557]],[[760,760,784,784,760],[509,533,533,509,509]],[[691,691,715,715,691],[570,594,594,570,570]],[[644,644,668,668,644],[515,539,539,515,515]],[[669,669,693,693,669],[500,524,524,500,500]],[[633,633,657,657,633],[483,507,507,483,483]],[[533,533,557,557,533],[453,477,477,453,453]],[[590,590,614,614,590],[384,408,408,384,384]],[[611,611,635,635,611],[416,440,440,416,416]],[[589,589,613,613,589],[414,438,438,414,414]],[[533,533,557,557,533],[557,581,581,557,557]],[[431,431,455,455,431],[653,677,677,653,653]],[[495,495,519,519,495],[743,767,767,743,743]],[[506,506,530,530,506],[737,761,761,737,737]],[[327,327,351,351,327],[709,733,733,709,709]],[[378,378,402,402,378],[733,757,757,733,733]],[[272,272,296,296,272],[580,604,604,580,580]],[[242,242,266,266,242],[540,564,564,540,540]],[[242,242,266,266,242],[507,531,531,507,507]],[[418,418,442,442,418],[434,458,458,434,434]],[[323,323,347,347,323],[428,452,452,428,428]],[[358,358,382,382,358],[385,409,409,385,385]],[[642,642,666,666,642],[332,356,356,332,332]],[[752,752,776,776,752],[600,624,624,600,600]],[[396,396,420,420,396],[585,609,609,585,585]],[[421,421,445,445,421],[571,595,595,571,571]],[[517,517,541,541,517],[668,692,692,668,668]],[[567,567,591,591,567],[641,665,665,641,641]],[[664,664,688,688,664],[404,428,428,404,404]],[[516,516,540,540,516],[354,378,378,354,354]],[[416,416,440,440,416],[535,559,559,535,535]],[[475,475,499,499,475],[433,457,457,433,433]],[[575,575,599,599,575],[449,473,473,449,449]],[[597,597,621,621,597],[335,359,359,335,335]],[[627,627,651,651,627],[310,334,334,310,310]],[[241,241,265,265,241],[690,714,714,690,690]],[[753,753,777,777,753],[576,600,600,576,576]],[[684,684,708,708,684],[637,661,661,637,637]],[[593,593,617,617,593],[695,719,719,695,695]],[[284,284,308,308,284],[435,459,459,435,435]],[[301,301,325,325,301],[451,475,475,451,451]],[[581,581,605,605,581],[522,546,546,522,522]],[[460,460,484,484,460],[556,580,580,556,556]]],
				       'These are fission tracks. They start with an opening (the "<b>etch pit</b>") at the surface which can be seen in reflected light, and end with a <b>tail</b> which extends up to 15 microns into the grain, as can be seen by focusing into the transmitted stack of images.'),
			     new grain('Grain13',
				       [[[239,451,757,811,682,440,284,176,239],[698,783,645,464,263,317,434,593,698]],[[668,668,692,692,668],[581,605,605,581,581]],[[620,620,644,644,620],[604,628,628,604,604]],[[611,611,635,635,611],[539,563,563,539,539]],[[557,557,581,581,557],[599,623,623,599,599]],[[522,522,546,546,522],[591,615,615,591,591]],[[457,457,481,481,457],[636,660,660,636,636]],[[253,253,277,277,253],[566,590,590,566,566]],[[330,330,354,354,330],[497,521,521,497,497]],[[535,535,559,559,535],[365,389,389,365,365]],[[537,537,561,561,537],[407,431,431,407,407]]],
				       'These features may or may not be fission tracks. They are too small to distinguish a tail. In this can a <b>subjective</b> decision has to be made whether or not to count these features. The exact <b>cutoff</b> length below which one decides not to count a feature is not important as long as <b>the same cutoff</b> is used for all grains.')];

	samples[1].grains = [new grain('Grain11',
			               [[[323,501,675,481,323],[153,382,292,58,153]]],
			               'These are NOT fission tracks but <b>crystal defects</b>. They go deeper than fission tracks and show a preferential alignment. In contrast, fission tracks have random orientations.')];

	samples[2].grains = [new grain('Grain04',
				       [[[],[]]],
				       'After verifying the presence of a randomly oriented tail in transmitted light, the tracks can be counted by clicking on the etch pit in relfected light. Tracks whose etch pits fall outside the region of interest (white polygon) should not be counted.'),
			     new grain('Grain05',
				       [[[],[]]],
				       'Counting errors can be corrected by clicking to the upper left and the lower right of the erroneous points and then clicking the trash bin symbol.'),
			     new grain('Grain06',
				       [[[],[]]],
				       "Once you are happy with the selected points, you can submit them to geochron@home and start counting the next randomly selected grain.")];

	return samples;
    }

});

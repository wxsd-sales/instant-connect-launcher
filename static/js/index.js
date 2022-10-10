/*
function updateSummary(response){
  var today = new Date();
  var time = ('0' + today.getHours()).substr(-2) + ":" + ('0' + today.getMinutes()).substr(-2) + ":" + ('0' + today.getSeconds()).substr(-2);
  text = time + " - " + response;
  var summary_area = document.getElementById("summary");
  summary_area.value = text + "\n" + summary_area.value;
  summary_area.scrollTop = 0;
}*/

var myHostUrl;
var myGuestUrl;
var meetingStartTime = null;
var meetingDuration = null;

function makeDanger(){
  $('#main-notification').removeClass('is-primary');
  $('#main-notification').addClass('is-danger');
}

function makePrimary(){
  $('#main-notification').addClass('is-primary');
  $('#main-notification').removeClass('is-danger');
}

function makeDefault(){
  $('#main-notification').removeClass('is-primary');
  $('#main-notification').removeClass('is-danger');
}



function startInstantConnectMeeting(){
  meetingStartTime = $('.my-calendar').val();
  meetingDuration = parseInt($('#duration').val())
  let options = {command: "start_meeting", 
                 environment: environment,
                 duration: meetingDuration,
                 start_time: meetingStartTime,
                 timezone: Intl.DateTimeFormat().resolvedOptions().timeZone }
  console.log(options);
  $.post('/command', JSON.stringify(options)).done(function (response) {
    console.log(response);
    let jresp = JSON.parse(response);
    if(jresp.data){
      console.log(jresp.data["host_url"]);
      console.log(jresp.data["guest_url"]);
      myHostUrl = jresp.data["host_url"];
      myGuestUrl = jresp.data["guest_url"];
      if(jresp.data["delay"]){
        $('#main-notification').text('Future Instant Connect Meeting created. An Email with the details has been sent to you.');
        $('#copy-join-buttons').hide();
        $('#meeting-buttons').css('visibility', 'visible');
      } else {
        
        $('#main-notification').text('Created Instant Connect Meeting successfully.');
        $('#copy-join-buttons').show();
        $('#meeting-buttons').css('visibility', 'visible');
      }
    } else {
      console.log('startInstantConnectMeeting - failed');
      makeDanger();
      $('#main-notification').text('Failed to create Instant Connect Meeting.');
    }
    $('#start').removeClass('is-loading');
  });
}


$('document').ready(function() {

  $('#webex-avatar').attr('src', webexAvatar);

  $("#start").on('click', function(e) {
    $('#meeting-buttons').css('visibility', 'hidden');
    $('#start').addClass('is-loading');
    makeDefault();
    $('#main-notification').text('Creating Instant Connect Meeting.');
    $('#main-notification').css('visibility', 'visible');
    startInstantConnectMeeting();
  });

  $("#copy").on('click', function(e) {
    navigator.clipboard.writeText(myHostUrl);
    makeDefault();
    $('#main-notification').text('Copied Host Meeting URL to clipboard.');
  });

  $('#join').on('click', function(e){
    window.open(myHostUrl, "_blank");
  })

  $('#email').on('click', function(e){
    let emailInput = $('#email-input').val().trim();
    if(emailInput){
      $('#email').addClass('is-loading');
      let options = {command: "email", 
                    url: myGuestUrl, 
                    email: emailInput,
                    duration: meetingDuration,
                    start_time: meetingStartTime,
                    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone}
      $.post('/command', JSON.stringify(options)).done(function (response) {
        console.log(response);
        let jresp = JSON.parse(response);
        if(jresp.data){
          console.log(jresp.data);
          makePrimary();
          $('#main-notification').text('Sent Guest URL emails successfully.');
        } else {
          console.log('POST /command: email - failed');
          makeDanger();
          let errText = 'Failed to send Guest URL emails.<br/>';
          errText += jresp.reason;
          $('#main-notification').html(errText);
        }
        $('#email').removeClass('is-loading');
      });
    } else {
      makeDanger();
      $('#main-notification').text('Guest Email input cannot be empty.');
    }
  })

  $('#logout').on('click', function(e){
    let redirectTo = "/logout?";
    if(window.location.pathname != "/"){
      redirectTo += `returnTo=${window.location.pathname.substring(1)}`;
    }
    window.location = redirectTo;
  })

})
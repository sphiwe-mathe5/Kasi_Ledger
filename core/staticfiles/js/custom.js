// to get current year
function getYear() {
    var currentDate = new Date();
    var currentYear = currentDate.getFullYear();
    document.querySelector("#displayYear").innerHTML = currentYear;
}

getYear();


$('.custom_slick_slider').slick({
    slidesToShow: 1,
    slidesToScroll: 1,
    dots: true,
    fade: true,
    adaptiveHeight: true,
    asNavFor: '.slick_slider_nav',
    responsive: [{
        breakpoint: 768,
        settings: {
            dots: false
        }
    }]
})

$('.slick_slider_nav').slick({
    slidesToShow: 3,
    slidesToScroll: 1,
    asNavFor: '.custom_slick_slider',
    centerMode: false,
    focusOnSelect: true,
    variableWidth: true
});


/** google_map js **/

function myMap() {
    var mapProp = {
        center: new google.maps.LatLng(40.712775, -74.005973),
        zoom: 18,
    };
    var map = new google.maps.Map(document.getElementById("googleMap"), mapProp);
}



function toggleMenu() {
    var navLinks = document.getElementById("nav-links");
    navLinks.classList.toggle("show");
  }
  let toggleButton = document.getElementById("toggleBtn");
  let toggleContainer = document.getElementById("toggleSlider");
  
  function showCategory(category) {
    // Hide both categories
    document.getElementById("animals").classList.remove("active-category");
    document.getElementById("food").classList.remove("active-category");
  
    // Show the selected category
    document.getElementById(category).classList.add("active-category");
  
    // Move the toggle button and adjust colors
    if (category === "food") {
      toggleButton.style.transform = "translateX(100%)";
      toggleContainer.classList.add("active");
    } else {
      toggleButton.style.transform = "translateX(0)";
      toggleContainer.classList.remove("active");
    }
  }
  function togglePopup() {
    const popup = document.getElementById("userPopup");
    if (popup.style.display === "none" || popup.style.display === "") {
      popup.style.display = "block"; // Show the popup
    } else {
      popup.style.display = "none"; // Hide the popup
    }
  }
  
  // Close the popup if clicking outside of it
  window.onclick = function (event) {
    const popup = document.getElementById("userPopup");
    if (!event.target.matches("#userIcon") && !popup.contains(event.target)) {
      popup.style.display = "none";
    }
  };
  document
    .getElementById("scrollToTopButton")
    .addEventListener("click", function () {
      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    });
  
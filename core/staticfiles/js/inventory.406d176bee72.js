let scanMode = "in";
let lastScanTime = 0;
const scanCooldown = 2000; 

function setScanMode(mode) {
  scanMode = mode;
  document.getElementById("scanInBtn").style.fontWeight =
    mode === "in" ? "bold" : "normal";
  document.getElementById("currentMode").textContent = `Current Mode: ${
    mode.charAt(0).toUpperCase() + mode.slice(1)
  }`;
  document.getElementById("productDetails").style.display =
    mode === "in" ? "block" : "none";
}

function onScanSuccess(decodedText, decodedResult) {
  const currentTime = new Date().getTime();
  if (currentTime - lastScanTime < scanCooldown) {
    console.log("Scan too soon, ignoring");
    return;
  }
  lastScanTime = currentTime;

  if (scanMode === "in" && !validateInputs()) {
    alert("Please fill in all product details before scanning in.");
    return;
  }

  //playBeep();

  if (scanMode === "bulk") {
    saveBulkProducts(decodedText);
  } else {
    saveProduct(decodedText, scanMode);
  }
}

function onScanFailure(error) {
  
}

let html5QrcodeScanner = new Html5QrcodeScanner("reader", {
  fps: 10,
  qrbox: { width: 250, height: 250 },
});
html5QrcodeScanner.render(onScanSuccess, onScanFailure);

function playBeep() {
  var audio = document.getElementById("beepAudio");
  audio.play();
}

function validateInputs() {
  if (scanMode !== "in") return true; 
  let productName = document.getElementById("productName").value;
  let productPrice = document.getElementById("productPrice").value;
  let productCost = document.getElementById("productCost").value;
  let productCategory = document.getElementById("productCategory").value;
  return productName && productPrice && productCost && productCategory;
}


let lastUpdate = new Date().toISOString();

function formatDate(dateString) {
  const date = new Date(dateString);
  const day = String(date.getDate()).padStart(2, "0");
  const month = date.toLocaleString("default", { month: "short" });
  const year = date.getFullYear();
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${day} ${month} ${year} ${hours}:${minutes}`;
}

function updateProduct(product) {
  const today = new Date().toISOString().split("T")[0];
  const productDate = new Date(product.date_added).toISOString().split("T")[0];

  if (productDate === today) {
    const tableContainer = $(`.table-container[data-date="${today}"]`);
    if (tableContainer.length) {
      const productElement = tableContainer.find(`#product-${product.id}`);
      const productHtml = `
                    <td>${product.name} ${product.original_quantity}</td>
                    <td>${product.barcode || "-"}</td>
                    <td>${
                      product.status === "IN" ? "In Stock" : "Out of Stock"
                    }</td>
                    <td>${product.category || "-"}</td>
                    <td>${product.quantity}</td>
                    <td>R${parseFloat(product.price).toFixed(2)}</td>
                    <td>R${parseFloat(product.cost).toFixed(2)}</td>
                    <td>${
                      product.status === "IN"
                        ? "-"
                        : formatDate(product.last_modified)
                    }</td>
                    <td>${formatDate(product.date_added)}</td>
                    <td>${product.profit_loss_message || "-"}</td>
                `;

      if (productElement.length) {
        productElement.html(productHtml);
      } else {
        const newRow = `<tr id="product-${product.id}">${productHtml}</tr>`;
        tableContainer.find(".product-table tbody").prepend(newRow);
      }

      updateTotals(tableContainer);
    }
  }
}

function updateTotals(tableContainer) {
  let dailyTotalPrice = 0;
  let dailyTotalCost = 0;
  let dailyTotalProfitLoss = 0;

  const today = new Date().toISOString().split("T")[0];

  tableContainer
    .find(".product-table tbody tr:not(.total-row)")
    .each(function () {
      const rowDate = $(this).find("td:eq(8)").text();
      const rowDateFormatted = new Date(rowDate).toISOString().split("T")[0];

      if (rowDateFormatted === today) {
        const price =
          parseFloat(
            $(this).find("td:eq(5)").text().replace("R", "").replace(/,/g, "")
          ) || 0;
        const cost =
          parseFloat(
            $(this).find("td:eq(6)").text().replace("R", "").replace(/,/g, "")
          ) || 0;
        const quantity = parseInt($(this).find("td:eq(4)").text()) || 0;

        dailyTotalPrice += price * quantity;
        dailyTotalCost += cost * quantity;
        dailyTotalProfitLoss = dailyTotalPrice - dailyTotalCost;
      }
    });

  updateMonthlyTotals();
}

function updateMonthlyTotals() {
  $(".table-container").each(function () {
    const monthYear = $(this).closest("section").find("h2").text();
    let monthlyTotalPrice = 0;
    let monthlyTotalCost = 0;
    let monthlyTotalProfitLoss = 0;

    $(this)
      .find(".total-row")
      .each(function () {
        monthlyTotalPrice +=
          parseFloat($(this).find("td:eq(1)").text().replace("R", "")) || 0;
        monthlyTotalCost +=
          parseFloat($(this).find("td:eq(2)").text().replace("R", "")) || 0;
        monthlyTotalProfitLoss +=
          parseFloat($(this).find("td:eq(4)").text().replace("R", "")) || 0;
      });

    const monthlyTotalsElement = $(this)
      .closest("section")
      .find(".monthly-totals");
    monthlyTotalsElement.html(`
                Monthly Totals: 
                Price: R${monthlyTotalPrice.toFixed(2)} | 
                Cost: R${monthlyTotalCost.toFixed(2)} |
                Profit/Loss: R${monthlyTotalProfitLoss.toFixed(2)}
            `);
  });
}


function fetchLatestProducts() {
  $.ajax({
    url: ENQUIRE,
    data: { last_update: lastUpdate },
    success: function (data) {
      data.products.forEach(updateProduct);
      if (data.products.length > 0) {
        lastUpdate = data.server_time;
      }
    },
    complete: function () {
      setTimeout(fetchLatestProducts, 5000); 
    },
  });
}


$(document).ready(function () {
  fetchLatestProducts(); 

  
});


function saveProduct(barcode, action) {
  let data = {
    barcode: barcode,
    action: action,
    csrfmiddlewaretoken: CSRF_TOKEN,
  };

  if (action === "in") {
    let quantity = parseInt(document.getElementById("productQuantity").value);
    let pricePerUnit = parseFloat(
      document.getElementById("productPrice").value
    );
    let costPerUnit = parseFloat(document.getElementById("productCost").value);

    data.name = document.getElementById("productName").value;
    data.price = (quantity * pricePerUnit).toFixed(2);
    data.cost = (quantity * costPerUnit).toFixed(2);
    data.quantity = quantity;
    data.category = document.getElementById("productCategory").value;
  } else if (action === "out") {
    data.quantity = 1;
  }

  $.ajax({
    url: SUBSCRIBE,
    type: "POST",
    data: data,
    success: function (response) {
        if (response.success) {
            playBeep();
            $("#result").html(
                `<p>Barcode: <strong>${barcode}</strong> (${response.status})</p>`
            );

            alert(response.message);
            if (action === "in") {
                document.getElementById("productName").value = "";
                document.getElementById("productPrice").value = "";
                document.getElementById("productCost").value = "";
                document.getElementById("productQuantity").value = "1";
                document.getElementById("productCategory").value = "";
            }
            
            fetchLatestProducts();
        } else {
            if (response.details) {
                switch(response.details.type) {
                    case 'no_subscription':
                    case 'inactive_subscription':
                        showSubscriptionModal(response.details);
                        break;
                    case 'limit_reached':
                        showLimitModal(response.details);
                        break;
                    default:
                        alert("Error: " + response.message);
                }
            } else {
                alert("Error: " + response.message);
            }
        }
    },
    error: function () {
        alert("Error communicating with the server.");
    },
});
}


function showSubscriptionModal(details) {
  const modalContent = `
      <div class="submodal-content">
          <div class="submodal-icon">🔔</div>
          <h3 class="submodal-title">${details.title}</h3>
          <p class="submodal-message">${details.description}</p>
          <a href="${details.action_url}" class="submodal-button">${details.action_text}</a>
      </div>
  `;
  
  $("#subscriptionModal")
      .html(modalContent)
      .show();
}

function showLimitModal(details) {
  document.getElementById("productLimit").textContent = details.limit;
  document.getElementById("resetDate").textContent = details.reset_date;
  document.getElementById("daysUntilReset").textContent = details.days_until_reset;
  document.getElementById("limitReachedModal").style.display = "block";
}

function closeLimitModal() {
  document.getElementById("limitReachedModal").style.display = "none";
}


window.onclick = function(event) {
  var modal = document.getElementById("limitReachedModal");
  if (event.target == modal) {
      modal.style.display = "none";
  }
}

document.addEventListener("DOMContentLoaded", function () {
  const urlParams = new URLSearchParams(window.location.search);
  const showAll = urlParams.get("show_all");
  const date = urlParams.get("date");

  if (showAll === "true" && date) {
    const targetElement = document.querySelector(
      `.table-container[data-date="${date}"]`
    );
    if (targetElement) {
      targetElement.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }
});

setScanMode("in");

document.addEventListener("DOMContentLoaded", function () {
  const searchInput = document.getElementById("searchInput");
  const categoryFilter = document.getElementById("categoryFilter");
  const statusFilter = document.getElementById("statusFilter");

  function filterTable() {
    const searchTerm = searchInput.value.toLowerCase();
    const categoryValue = categoryFilter.value.toLowerCase();
    const statusValue = statusFilter.value.toLowerCase();

    const tables = document.querySelectorAll(".product-table");

    tables.forEach((table) => {
      const rows = table.querySelectorAll("tbody tr:not(.total-row)");
      let visibleCount = 0;

      rows.forEach((row) => {
        const nameCell = row.cells[0].textContent.toLowerCase();
        const categoryCell = row.cells[3].textContent.toLowerCase();
        const statusCell = row.cells[2].textContent.toLowerCase();

        const matchesSearch = nameCell.includes(searchTerm);
        const matchesCategory =
          !categoryValue || categoryCell.includes(categoryValue);
        const matchesStatus = !statusValue || statusCell.includes(statusValue);

        if (matchesSearch && matchesCategory && matchesStatus) {
          row.style.display = "";
          visibleCount++;
        } else {
          row.style.display = "none";
        }
      });

      
      const dateContainer = table.closest(".table-container");
      if (dateContainer) {
        const date = dateContainer.dataset.date;
        const countElement =
          dateContainer.previousElementSibling.previousElementSibling;
        if (countElement && countElement.querySelector(".product-count")) {
          countElement.querySelector(".product-count").textContent =
            visibleCount;
        }
      }

      
      const totalRow = table.querySelector(".total-row");
      if (totalRow) {
        totalRow.style.display = "";
      }
    });
  }

  
  searchInput.addEventListener("input", filterTable);
  categoryFilter.addEventListener("change", filterTable);
  statusFilter.addEventListener("change", filterTable);
});

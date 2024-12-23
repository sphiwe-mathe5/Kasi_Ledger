let cart = {};
let lastScanTime = 0;
let currentTotal = 0;
const scanCooldown = 2000; // 2 seconds cooldown between scans

// Initialize HTML5 QR code scanner
const html5QrcodeScanner = new Html5QrcodeScanner("reader", {
  fps: 10,
  qrbox: { width: 250, height: 250 },
});

function onScanSuccess(decodedText, decodedResult) {
  const currentTime = new Date().getTime();
  if (currentTime - lastScanTime < scanCooldown) {
    console.log("Scan too soon, ignoring");
    return;
  }
  lastScanTime = currentTime;

  updateScannerStatus("Scanning...", "success");
  checkProduct(decodedText);
}

function onScanFailure(error) {
  // Handle scan failure silently
}

// Render the scanner
html5QrcodeScanner.render(onScanSuccess, onScanFailure);

function updateScannerStatus(message, type) {
  const statusDiv = document.getElementById("scanner-status");
  statusDiv.textContent = message;
  statusDiv.className = type;
  setTimeout(() => {
    statusDiv.textContent = "";
    statusDiv.className = "";
  }, 3000);
}

function playBeep() {
  var audio = document.getElementById("beepAudio");
  audio.play();
}

function checkProduct(barcode) {
    $.ajax({
      url: CHECK_PRODUCT_URL,
      type: "GET",
      data: { barcode: barcode },
      success: function (response) {
        if (response.success) {
          if (response.product.quantity > 0) {
            playBeep();  // Only play beep on successful product addition
            addToCart(response.product);
            updateScannerStatus("Product added to cart!", "success");
          } else {
            updateScannerStatus("Product out of stock!", "error");
          }
        } else {
          updateScannerStatus("Product not found", "error");
        }
      },
      error: function () {
        updateScannerStatus("Error checking product", "error");
      },
    });
  }

function addToCart(product) {
  const maxQuantity = product.quantity; // Get available quantity

  if (cart[product.barcode]) {
    if (cart[product.barcode].quantity >= maxQuantity) {
      updateScannerStatus("Maximum available quantity reached!", "error");
      return;
    }
    cart[product.barcode].quantity += 1;
    cart[product.barcode].total =
      cart[product.barcode].quantity * product.price;
    updateCartRow(product.barcode);
  } else {
    cart[product.barcode] = {
      name: product.name,
      price: product.price,
      quantity: 1,
      total: product.price,
      maxQuantity: maxQuantity,
    };
    addCartRow(product.barcode);
  }
  updateTotal();
}

function addCartRow(barcode) {
  const item = cart[barcode];
  const row = `
          <tr data-barcode="${barcode}">
              <td>${item.name}</td>
              <td>R${item.price.toFixed(2)}</td>
              <td>${item.quantity}</td>
              <td>R${item.total.toFixed(2)}</td>
              <td>
                  <span class="remove-item" onclick="removeItem('${barcode}')">❌</span>
              </td>
          </tr>
      `;
  $("#pos-table tbody").append(row);
}

function updateCartRow(barcode) {
  const item = cart[barcode];
  const row = $(`tr[data-barcode="${barcode}"]`);
  row.find("td:nth-child(3)").text(item.quantity);
  row.find("td:nth-child(4)").text(`R${item.total.toFixed(2)}`);
}

function updateTotal() {
  const total = Object.values(cart).reduce((sum, item) => sum + item.total, 0);
  $(".total-amount").text(`R${total.toFixed(2)}`);
}

function removeItem(barcode) {
  delete cart[barcode];
  $(`tr[data-barcode="${barcode}"]`).remove();
  updateTotal();
}

function clearCart() {
  cart = {};
  $("#pos-table tbody").empty();
  updateTotal();
}


function calculateChange() {
  const moneyRendered = parseFloat(document.getElementById('moneyRendered').value) || 0;
  const change = moneyRendered - currentTotal;
  
  document.getElementById('changeAmount').textContent = 
      change >= 0 ? `R${change.toFixed(2)}` : 'Insufficient amount';
  
  if (change < 0) {
      document.getElementById('changeAmount').style.color = '#dc3545';
  } else {
      document.getElementById('changeAmount').style.color = '#28a745';
  }
}

// Update total and recalculate change


function processSale() {
  if (Object.keys(cart).length === 0) {
      alert("Cart is empty");
      return;
  }

  const moneyRendered = parseFloat($("#moneyRendered").val()) || 0;
  const totalAmount = parseFloat($(".total-amount").text().replace("R", ""));

  if (moneyRendered < totalAmount) {
      alert("Insufficient money rendered");
      return;
  }

  // Show loader before starting the process
  showLoader();

  const saleData = {
      items: Object.entries(cart).map(([barcode, item]) => ({
          barcode: barcode,
          quantity: item.quantity,
          price: item.price,
      })),
      total_amount: totalAmount,
      money_rendered: moneyRendered,
      email: $("#customerEmail").val(),
      csrfmiddlewaretoken: CSRF_TOKEN,
  };

  $.ajax({
      url: PROCESS_SALE_URL,
      type: "POST",
      data: JSON.stringify(saleData),
      contentType: "application/json",
      success: function (response) {
        if (response.success) {
          // Show success state with checkmark
          hideLoader(true);
          
          // Handle successful sale
          showReceipt(response.receipt_data);
          clearCart();
          
          // Wrap all post-receipt actions in a timeout to ensure they happen after receipt
          setTimeout(() => {
              // Show email confirmation if applicable
              if (response.email_sent && $("#customerEmail").val()) {
                  alert("Receipt has been sent to " + $("#customerEmail").val());
              }
              
              // Reset form and cart only after alert is shown
              $("#customerEmail").val("");
              $("#moneyRendered").val("");
              $("#changeAmount").text("R0.00");
              cart = {};
              updateCartDisplay();
              
              // Clear the cart display
              clearCart();
          }, 1000); // Wait 1 second after receipt shows
      } else {
          // Hide loader and show error
          hideLoader(false);
          alert("Error: " + response.message);
      }
      },
      error: function (xhr, status, error) {
          // Hide loader and show error
          hideLoader(false);
          alert("Error processing sale: " + error);
      },
  });


function showReceipt(receiptData) {
    // Create receipt HTML
    let receiptHtml = `
        <div style="font-family: monospace; padding: 20px; max-width: 400px; margin: auto;">
            <h2 style="text-align: center;">Receipt</h2>
            <p>Date: ${receiptData.date}</p>
            <hr>
            <table style="width: 100%;">
                <tr>
                    <th>Item</th>
                    <th>Qty</th>
                    <th>Price</th>
                    <th>Total</th>
                </tr>
    `;

    receiptData.items.forEach((item) => {
        receiptHtml += `
            <tr>
                <td>${item.name}</td>
                <td>${item.quantity}</td>
                <td>R${item.price.toFixed(2)}</td>
                <td>R${item.total.toFixed(2)}</td>
            </tr>
        `;
    });

    receiptHtml += `
            <tr><td colspan="4"><hr></td></tr>
            <tr>
                <td colspan="3"><strong>Total:</strong></td>
                <td><strong>R${receiptData.total.toFixed(2)}</strong></td>
            </tr>
            <tr>
                <td colspan="3"><strong>Money Rendered:</strong></td>
                <td><strong>R${receiptData.money_rendered.toFixed(2)}</strong></td>
            </tr>
            <tr>
                <td colspan="3"><strong>Change:</strong></td>
                <td><strong>R${receiptData.change.toFixed(2)}</strong></td>
            </tr>
        </table>
        <hr>
        <p style="text-align: center;">Thank you for your purchase!</p>
        </div>
    `;

    // Show in popup window
    const receiptWindow = window.open("", "Receipt", "width=400,height=600");
    receiptWindow.document.body.innerHTML = receiptHtml;

    // Optional: Print automatically
    receiptWindow.print();
  }
}

var modal = document.getElementById("calculatorModal");
var btn = document.getElementById("openCalculatorBtn");
var span = document.getElementsByClassName("close")[0];

// Open the modal when the user clicks the button
btn.onclick = function () {
  modal.style.display = "block";
};

// Close the modal when the user clicks on <span> (x)
span.onclick = function () {
  modal.style.display = "none";
};

// Close the modal when the user clicks outside of the modal
window.onclick = function (event) {
  if (event.target == modal) {
    modal.style.display = "none";
  }
};

// Calculator functionality
let currentInput = "0";
let operator = null;
let previousInput = "";

function appendNumber(number) {
  if (currentInput === "0") {
    currentInput = number.toString();
  } else {
    currentInput += number;
  }
  document.getElementById("result").textContent = currentInput;
}

function appendOperator(op) {
  if (operator !== null) return;
  operator = op;
  previousInput = currentInput;
  currentInput = "";
}

function clearResult() {
  currentInput = "0";
  previousInput = "";
  operator = null;
  document.getElementById("result").textContent = currentInput;
}

function calculateResult() {
  if (operator === null || currentInput === "") return;
  let result;
  switch (operator) {
    case "+":
      result = parseFloat(previousInput) + parseFloat(currentInput);
      break;
    case "-":
      result = parseFloat(previousInput) - parseFloat(currentInput);
      break;
    case "*":
      result = parseFloat(previousInput) * parseFloat(currentInput);
      break;
    case "/":
      if (currentInput === "0") {
        alert("Cannot divide by zero");
        return;
      }
      result = parseFloat(previousInput) / parseFloat(currentInput);
      break;
  }
  currentInput = result.toString();
  operator = null;
  previousInput = "";
  document.getElementById("result").textContent = currentInput;
}



function showLoader() {
  const overlay = document.querySelector('.loader-overlay');
  const spinner = overlay.querySelector('.spinner');
  const checkmark = overlay.querySelector('.checkmark');
  const text = overlay.querySelector('.processing-text');
  
  overlay.style.display = 'flex';
  spinner.style.display = 'block';
  checkmark.style.display = 'none';
  text.textContent = 'Processing Sale...';
}

function hideLoader(success = true) {
  const overlay = document.querySelector('.loader-overlay');
  const spinner = overlay.querySelector('.spinner');
  const checkmark = overlay.querySelector('.checkmark');
  const text = overlay.querySelector('.processing-text');

  if (success) {
    spinner.style.display = 'none';
    checkmark.style.display = 'block';
    text.textContent = 'Sale Complete!';
    
    setTimeout(() => {
      overlay.style.display = 'none';
      checkmark.style.display = 'none';
    }, 1500);
  } else {
    overlay.style.display = 'none';
  }
}
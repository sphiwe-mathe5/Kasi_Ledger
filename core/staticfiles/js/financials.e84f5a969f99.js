function updateFinancials() {
    const monthSelect = document.getElementById("month-select");
    const selectedMonth = monthSelect.value;
    const salesInput = document.getElementById("id_sales");
    const costInput = document.getElementById("id_cost_of_sales");

    salesInput.value = "";
    costInput.value = "";

    // Remove JSON.parse since data is already parsed
    if (selectedMonth in monthlyTotals) {
        salesInput.value = parseFloat(monthlyTotals[selectedMonth].price).toFixed(2);
        costInput.value = parseFloat(monthlyTotals[selectedMonth].cost).toFixed(2);
    }
}

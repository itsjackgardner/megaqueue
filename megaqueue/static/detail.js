const renameDetails = document.getElementById("rename-details");
const renameForm = document.getElementById("rename-form");

if (renameDetails && renameForm) {
  renameDetails.addEventListener("toggle", function () {
    renameForm.style.display = this.open ? "" : "none";
  });
}

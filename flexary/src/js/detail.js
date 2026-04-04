const loading = document.getElementById("loading");
const container = document.getElementById("container");
addEventListener("py:ready", () => {
  loading.close();
  container.classList.remove("d-none");
});
loading.showModal();

(function () {
  function getSwal() {
    if (typeof Swal === "undefined") return null;
    return Swal.mixin({
      customClass: {
        confirmButton: "btn btn-success ms-2",
        cancelButton: "btn btn-danger"
      },
      buttonsStyling: false
    });
  }

  function attachConfirmToForm(form, opts) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();

      const swalBS = getSwal();
      if (!swalBS) {
        // fallback if SweetAlert isn't loaded
        if (confirm(opts.fallbackText || "Are you sure?")) form.submit();
        return;
      }

      swalBS.fire({
        title: opts.title || "Are you sure?",
        text: opts.text || "This action cannot be undone.",
        icon: opts.icon || "warning",
        showCancelButton: true,
        confirmButtonText: opts.confirmText || "Yes",
        cancelButtonText: opts.cancelText || "Cancel",
        reverseButtons: true
      }).then((result) => {
        if (result.isConfirmed) {form.submit()}
        else if (result.dismiss === Swal.DismissReason.cancel) {
          swalBS.fire({
            title: "Cancelled",
            text: "Your action has been cancelled.",
            icon: "info",
            timer: 2000,
            showConfirmButton: false
          });
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    // DELETE (forms)
    document.querySelectorAll("form[data-swal='delete']").forEach((form) => {
      const name = form.getAttribute("data-swal-name") || "this item";
      attachConfirmToForm(form, {
        title: "Delete?",
        text: `Delete ${name}? You won't be able to revert this!`,
        icon: "warning",
        confirmText: "Yes, delete it!",
        cancelText: "No, cancel",
        fallbackText: `Delete ${name}?`
      });
    });

    // SAVE (forms)
    document.querySelectorAll("form[data-swal='save']").forEach((form) => {
      attachConfirmToForm(form, {
        title: "Save changes?",
        text: "Do you want to save these changes?",
        icon: "question",
        confirmText: "Yes, save",
        cancelText: "Cancel",
        fallbackText: "Save changes?"
      });
    });

    // ADD/CREATE (forms)
    document.querySelectorAll("form[data-swal='create']").forEach((form) => {
      attachConfirmToForm(form, {
        title: "Create?",
        text: "Do you want to create this item?",
        icon: "question",
        confirmText: "Yes, create",
        cancelText: "Cancel",
        fallbackText: "Create this item?"
      });
    });
  });
})();
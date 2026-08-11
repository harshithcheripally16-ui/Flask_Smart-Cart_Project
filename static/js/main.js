/* static/js/main.js - Swiggy-Inspired Interactive UI Animations */

document.addEventListener('DOMContentLoaded', () => {
    
    // 1. Live Image File Preview for Forms
    const fileInputs = document.querySelectorAll('input[type="file"][accept*="image"]');
    fileInputs.forEach(input => {
        input.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(event) {
                    let previewContainer = input.closest('.mb-3') || input.parentElement;
                    let existingPreview = previewContainer.querySelector('.live-img-preview');
                    
                    if (!existingPreview) {
                        existingPreview = document.createElement('img');
                        existingPreview.className = 'live-img-preview img-thumbnail mt-2 rounded-3 shadow-sm';
                        existingPreview.style.maxWidth = '130px';
                        existingPreview.style.maxHeight = '130px';
                        existingPreview.style.objectFit = 'cover';
                        existingPreview.style.border = '2px solid var(--swiggy-orange)';
                        previewContainer.appendChild(existingPreview);
                    }
                    existingPreview.src = event.target.result;
                    existingPreview.style.display = 'block';
                };
                reader.readAsDataURL(file);
            }
        });
    });

    // 2. Submit Button Loading State with Swiggy Spinner
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn && !form.dataset.noSpinner) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = `
                    <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                    Processing...
                `;
            }
        });
    });

    // 3. Auto-Dismiss Flash Alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (window.bootstrap && bootstrap.Alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            } else {
                alert.style.transition = 'opacity 0.5s ease';
                alert.style.opacity = '0';
                setTimeout(() => alert.remove(), 500);
            }
        }, 5000);
    });

    // 4. Instant Client-Side Table Search Highlighting
    const clientSearchInput = document.getElementById('clientSearchInput');
    const tableBody = document.querySelector('table tbody');
    
    if (clientSearchInput && tableBody) {
        clientSearchInput.addEventListener('keyup', function() {
            const filter = clientSearchInput.value.toLowerCase();
            const rows = tableBody.getElementsByTagName('tr');
            
            for (let i = 0; i < rows.length; i++) {
                const textContent = rows[i].textContent.toLowerCase();
                if (textContent.includes(filter)) {
                    rows[i].style.display = '';
                } else {
                    rows[i].style.display = 'none';
                }
            }
        });
    }

    // 5. Swiggy Delete Confirmation Modal Handling
    document.addEventListener('click', function(e) {
        const trigger = e.target.closest('.btn-delete-trigger');
        if (trigger) {
            e.preventDefault();
            const productName = trigger.getAttribute('data-product-name') || 'this product';
            const deleteUrl = trigger.getAttribute('data-delete-url');

            const nameSpan = document.getElementById('deleteModalProductName');
            const confirmLink = document.getElementById('confirmDeleteLink');

            if (nameSpan) nameSpan.textContent = productName;
            if (confirmLink) confirmLink.setAttribute('href', deleteUrl);

            const modalEl = document.getElementById('deleteConfirmModal');
            if (modalEl && window.bootstrap) {
                const deleteModal = new bootstrap.Modal(modalEl);
                deleteModal.show();
            }
        }
    });

});

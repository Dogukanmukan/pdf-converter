document.addEventListener('DOMContentLoaded', () => {
    const fileInputs = document.querySelectorAll('input[type="file"]');
    const fileLabels = document.querySelectorAll('.file-label');
    const fileNames = document.querySelectorAll('.file-name');
    const forms = document.querySelectorAll('.conversion-form');
    let conversionInProgress = false;

    // File input handling
    fileInputs.forEach((fileInput, index) => {
        const fileLabel = fileLabels[index];
        const fileName = fileNames[index];
        const form = forms[index];
        const submitButton = form.querySelector('button[type="submit"]');

        fileInput.addEventListener('change', (e) => {
            if (conversionInProgress) return;
            
            const file = e.target.files[0];
            if (file) {
                fileName.textContent = file.name;
                submitButton.disabled = false;
            } else {
                resetInput(fileName, submitButton);
            }
        });

        fileLabel.addEventListener('dragover', (e) => {
            e.preventDefault();
            if (!conversionInProgress) {
                fileLabel.classList.add('dragover');
            }
        });

        fileLabel.addEventListener('dragleave', () => {
            fileLabel.classList.remove('dragover');
        });

        fileLabel.addEventListener('drop', (e) => {
            e.preventDefault();
            if (!conversionInProgress) {
                fileLabel.classList.remove('dragover');
                const file = e.dataTransfer.files[0];
                
                // Check file type
                const acceptedTypes = fileInput.accept.split(',');
                if (acceptedTypes.some(type => file.name.toLowerCase().endsWith(type.replace('.', '').toLowerCase()))) {
                    fileInput.files = e.dataTransfer.files;
                    fileName.textContent = file.name;
                    submitButton.disabled = false;
                } else {
                    showNotification('Desteklenmeyen dosya formatı', 'error');
                }
            }
        });
    });

    // Form submission handling
    forms.forEach(form => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (conversionInProgress) return;

            const submitButton = form.querySelector('button[type="submit"]');
            const fileInput = form.querySelector('input[type="file"]');
            const fileName = form.querySelector('.file-name');
            
            if (!fileInput.files[0]) {
                showNotification('Lütfen bir dosya seçin', 'error');
                return;
            }

            conversionInProgress = true;
            submitButton.disabled = true;
            submitButton.innerHTML = 'Dönüştürülüyor...';

            try {
                const formData = new FormData(form);
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    throw new Error('Dönüşüm sırasında bir hata oluştu');
                }

                const blob = await response.blob();
                const downloadUrl = URL.createObjectURL(blob);
                const downloadLink = document.createElement('a');
                downloadLink.href = downloadUrl;
                downloadLink.download = fileInput.files[0].name.replace(/\.[^/.]+$/, '') + 
                    (form.querySelector('input[name="type"]').value === 'pdf-to-img' ? '.zip' : '.pdf');
                downloadLink.click();
                URL.revokeObjectURL(downloadUrl);

                showNotification('Dönüşüm başarılı!', 'success');
                resetInput(fileName, submitButton);
            } catch (error) {
                showNotification(error.message, 'error');
                submitButton.disabled = false;
            } finally {
                conversionInProgress = false;
                submitButton.innerHTML = submitButton.dataset.originalText || 
                    (form.querySelector('input[name="type"]').value === 'pdf-to-img' ? 'Resme Dönüştür' : 'PDF\'e Dönüştür');
            }
        });
    });

    function resetInput(fileName, submitButton) {
        fileName.textContent = 'Dosya seçilmedi';
        submitButton.disabled = true;
    }

    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        document.body.appendChild(notification);

        setTimeout(() => {
            notification.classList.add('show');
        }, 100);

        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    // Initialize submit button texts
    forms.forEach(form => {
        const submitButton = form.querySelector('button[type="submit"]');
        submitButton.dataset.originalText = submitButton.innerHTML;
    });
});

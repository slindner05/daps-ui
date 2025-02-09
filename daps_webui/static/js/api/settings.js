async function getSettings() {
  try {
    const response = await fetch('/get-settings');
    const data = await response.json();
    if (data.success) {
      return data;
    }
    throw new Error('Error fetching settings: ' + data.message);
  } catch (error) {
    console.error('Error', error);
    throw error;
  }
}

async function saveSettings(requestBody) {
  try {
    const response = await fetch('/save-settings', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });
    const data = await response.json();
    if (data.success) {
      return data;
    }
    throw new Error('Error saving settings: ' + data.message);
  } catch (error) {
    console.error('Error', error);
    throw error;
  }
}

async function testInstanceConnection(requestBody) {
  try {
    const response = await fetch('/test-connection', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });
    const data = await response.json();
    if (data.success) {
      return data;
    }
    throw new Error('Error testing connection: ' + data.message);
  } catch (error) {
    console.error('Error', error);
    throw error;
  }
}

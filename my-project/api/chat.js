const { RsnChat } = require('rsnchat');

const ai = new RsnChat('rsnai_EEboyMMYPoxnPFpIRpEjsmaZ');

rsnchat.gpt4("Hello, what is your name?").then((response) => {
  console.log(response.message);
});

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  console.log("Request received:", req.method, req.body);

  if (req.method === 'POST') {
    const { prompt, model } = req.body;
    if (!prompt || !model) {
      console.error("Missing prompt or model");
      return res.status(400).json({ error: 'Missing prompt or model' });
    }

    try {
      let response;
      switch (model) {
        case 'gpt4':
          response = await ai.gpt4(prompt);
          break;
        case 'gemini':
          response = await ai.gemini(prompt);
          break;
        default:
          response = await ai.gpt(prompt);
      }
      console.log("Response from AI:", response);
      res.status(200).json({ response });
    } catch (error) {
      console.error("Error from AI service:", error.message);
      res.status(500).json({ error: error.message });
    }
  } else {
    console.error("Method not allowed");
    res.status(405).json({ error: 'Method not allowed' });
  }
};

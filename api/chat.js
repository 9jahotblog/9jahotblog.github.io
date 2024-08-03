const { RsnChat } = require('rsnchat');

const ai = new RsnChat('rsnai_EEboyMMYPoxnPFpIRpEjsmaZ');

module.exports = async (req, res) => {
  if (req.method === 'POST') {
    const { prompt, model } = req.body;
    if (!prompt || !model) {
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
      res.status(200).json({ response });
    } catch (error) {
      res.status(500).json({ error: error.message });
    }
  } else {
    res.status(405).json({ error: 'Method not allowed' });
  }
};

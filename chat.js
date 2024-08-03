// api/chat.js
const { RsnChat } = require('rsnchat');

const ai = new RsnChat('rsnai_EEboyMMYPoxnPFpIRpEjsmaZ');

module.exports = async (req, res) => {
  if (req.method === 'POST') {
    const { prompt, model } = req.body;
    try {
      let response;
      if (model === 'gpt4') {
        response = await ai.gpt4(prompt);
      } else if (model === 'gemini') {
        response = await ai.gemini(prompt);
      } else {
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

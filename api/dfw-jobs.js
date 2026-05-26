module.exports = async (req, res) => {

  try {

    const response = await fetch(
      'https://api.jobdatalake.com/v1/jobs?q=security+officer&location=Dallas&per_page=10&sort_by=posted_at:desc',
      {
        headers: {
          'X-API-Key': process.env.JOBDATALAKE_API_KEY
        }
      }
    );

    const data = await response.json();

    res.status(200).json(data);

  } catch (error) {

    res.status(500).json({
      error: error.message
    });

  }

};

from pyspark.sql import SparkSession
from pyspark.ml.feature import CountVectorizer, IDF, Tokenizer
from pyspark.sql.types import StructType, StructField, StringType
from pyspark.mllib import *
from pyspark.sql import SQLContext
from pyspark.sql.functions import udf, col
import findspark
findspark.init()


session = SparkSession.builder.appName("tfidf").getOrCreate()
sc = session.sparkContext

# define the schema of the review table
schema = StructType([
    StructField("reviewId", StringType(), True),
    StructField("asin", StringType(), True),
    StructField("reviewerId", StringType(), True),
    StructField("helpful", StringType(), True),
    StructField("rating", StringType(), True),
    StructField("summary", StringType(), True),
    StructField("reviewText", StringType(), True),
    StructField("createdAt", StringType(), True),
    StructField("updatedAt", StringType(), True)])

reviews = session.read.csv(
    "hdfs:///DBProject/review.csv", header=False, sep="\t", schema=schema)
# drop the reviews with NA reviewText
reviews = reviews.na.drop(subset=["reviewText"])

# convert reviewText to words
tokenizer = Tokenizer(inputCol="reviewText", outputCol="reviewWords")
tokenized_reviews = tokenizer.transform(reviews)
tokenized_reviews.show(1)

# get tf
cv = CountVectorizer(inputCol="reviewWords",
                     outputCol="rawFeatures")
model = cv.fit(tokenized_reviews)
featurizedData = model.transform(tokenized_reviews)
featurizedData.show(1)

# get idf
idf = IDF(inputCol="rawFeatures", outputCol="features")
idfModel = idf.fit(featurizedData)
rescaledData = idfModel.transform(featurizedData)
rescaledData.show(1)

vocab = model.vocabulary

# reformat the tfidf


def save_as_string(vector):
    words = ""
    for (i, tfidf) in zip(vector.indices, vector.values):
        temp = vocab[i] + ":" + str(float(tfidf)) + ", "
        words += temp
    return words[:-2]


output = rescaledData.select('reviewerID', 'asin', 'createdAt', 'features').rdd.map(
    lambda x: [x[0], x[1], x[2], save_as_string(x[3])])

print(output.take(2))

output_df = session.createDataFrame(
    output, ['reviewerID', 'asin', 'createdAt', 'tfidf'])
output_df.write.format("csv").save("hdfs:///DBProject/tfidf_output")

session.stop()

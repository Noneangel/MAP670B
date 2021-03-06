from pyspark import SparkContext
import loadFiles as lf
import numpy as np
from random import randint
from  pyspark.mllib.classification import NaiveBayes
from functools import partial
from pyspark.mllib.linalg import SparseVector
from pyspark.mllib.regression import LabeledPoint
sc = SparkContext(appName="Simple App")

from sklearn.cross_validation import KFold


def createBinaryLabeledPoint(doc_class,dictionary):
	words=doc_class[0].strip().split(' ')
	#create a binary vector for the document with all the words that appear (0:does not appear,1:appears)
	#we can set in a dictionary only the indexes of the words that appear
	#and we can use that to build a SparseVector
	vector_dict={}
	for w in words:
		vector_dict[dictionary[w]]=1
	return LabeledPoint(doc_class[1], SparseVector(len(dictionary),vector_dict))
def Predict(name_text,dictionary,model):
	words=name_text[1].strip().split(' ')
	vector_dict={}
	for w in words:
		if(w in dictionary):
			vector_dict[dictionary[w]]=1
	return (name_text[0], model.predict(SparseVector(len(dictionary),vector_dict)))
data,Y=lf.loadLabeled("./data/train")

#TODO : corssvalidation
n_folds = 5
kf = KFold(len(data), n_folds=n_folds, shuffle=True)
for folds_index, (train_index_array, test_index_array) in enumerate(kf):
	print("cross validation ({} out of {})".format(folds_index+1, n_folds))
	data_train, Y_train = [], []
	data_test, Y_test = [], []
	data_test_name = []
	for train_index in train_index_array:
		data_train.append(data[train_index])
		Y_train.append(Y[train_index])
	for j,test_index in enumerate(test_index_array):
		data_test.append(data[test_index])
		Y_test.append(Y[test_index])
		data_test_name.append(str(j) + "({})".format(Y[test_index]))

	print "\t", len(data_train)
	data_trainRDD=sc.parallelize(data_train,numSlices=16)
	#map data to a binary matrix
	#1. get the dictionary of the data
	#The dictionary of each document is a list of UNIQUE(set) words 
	lists=data_trainRDD.map(lambda x:list(set(x.strip().split(' ')))).collect()
	all=[]
	#combine all dictionaries together (fastest solution for Python)
	for l in lists:
		all.extend(l)
	dict=set(all)
	print "\t", len(dict)
	#it is faster to know the position of the word if we put it as values in a dictionary
	dictionary={}
	for i,word in enumerate(dict):
		dictionary[word]=i
	#we need the dictionary to be available AS A WHOLE throughout the cluster
	dict_broad=sc.broadcast(dictionary)
	#build labelled Points from data
	data_train_class=zip(data_train,Y_train)#if a=[1,2,3] & b=['a','b','c'] then zip(a,b)=[(1,'a'),(2, 'b'), (3, 'c')]
	dcRDD=sc.parallelize(data_train_class,numSlices=16)
	#get the labelled points
	labeledRDD=dcRDD.map(partial(createBinaryLabeledPoint,dictionary=dict_broad.value))
	#Train NaiveBayes
	model=NaiveBayes.train(labeledRDD)
	#broadcast the model
	mb=sc.broadcast(model)

	#TODO : testing of crossvalidation
	name_text=zip(data_test_name,data_test)
	#for each doc :(name,text):
	#apply the model on the vector representation of the text
	#return the name and the class
	predictions=sc.parallelize(name_text).map(partial(Predict,dictionary=dict_broad.value,model=mb.value)).collect()
	output=file('./classifications_test_{}.txt'.format(folds_index+1),'w')
	for x in predictions:
		output.write('%s\t%d\n'%x)
	output.close()

test,names=lf.loadUknown('./data/test')
name_text=zip(names,test)
#for each doc :(name,text):
#apply the model on the vector representation of the text
#return the name and the class
predictions=sc.parallelize(name_text).map(partial(Predict,dictionary=dict_broad.value,model=mb.value)).collect()

output=file('./classifications.txt','w')
for x in predictions:
	output.write('%s\t%d\n'%x)
output.close()






